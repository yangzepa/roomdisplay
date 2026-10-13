// 연구실 재실 문패: zepawork 서버를 롱폴링하다가 상태(seq)가 바뀌면
// 서버가 렌더링한 400x300 흑/적 비트맵을 받아 e-paper 에 그린다.
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <SPI.h>
#include <GxEPD2_3C.h>
#include <esp_wifi.h>
#include <esp_pm.h>
#include "secrets.h"

#define WAIT_SEC        55    // 서버 롱폴링 대기 시간(초). HTTPClient::setTimeout 이 uint16_t(ms)라 65초가 상한
#define LISTEN_INTERVAL 10    // 비컨 10개(약 1초)마다 한 번 깨어 수신
#define FAILS_TO_RECONNECT 3  // 서버 요청이 연속 이만큼 실패하면 WiFi 재연결
#define NO_OK_RESTART_MS (20UL * 60 * 1000)  // 이 시간 동안 한 번도 성공 못 하면 재부팅

#define EPD_SCK   25
#define EPD_MOSI  26
#define EPD_CS    27
#define EPD_DC    33
#define EPD_RST   32
#define EPD_BUSY  37
#define LCD_BL     4   // 온보드 LCD 백라이트
#define BAT_ADC   34   // 배터리 분압(1/2) 입력
#define BAT_EN    14   // 분압 회로 활성화(측정 시에만 HIGH)

GxEPD2_3C<GxEPD2_420c_GDEY042Z98, GxEPD2_420c_GDEY042Z98::HEIGHT>
  display(GxEPD2_420c_GDEY042Z98(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

static const int W = 400, H = 300;
static const size_t PLANE = W * H / 8;   // 15000 B
static uint8_t frame[PLANE * 2];          // 흑 평면 + 적 평면 (1 = 잉크)

Preferences prefs;
long shownSeq = -1;
volatile int lastDiscReason = 0;
uint32_t lastOkMs = 0;      // 마지막으로 서버 응답을 받은 시각
int failStreak = 0;         // 연속 실패 횟수
uint32_t totalFails = 0;    // 부팅 후 누적 실패(진단용으로 서버에 보고)

// 배터리 전압(mV). USB 연결 시에는 충전 전압(약 4.2V 이상)이 읽힌다.
int readBatteryMv() {
  pinMode(BAT_EN, OUTPUT);
  digitalWrite(BAT_EN, HIGH);
  delay(5);
  uint32_t sum = 0;
  for (int i = 0; i < 16; i++) sum += analogReadMilliVolts(BAT_ADC);
  digitalWrite(BAT_EN, LOW);
  return (int)(sum / 16) * 2;
}

void scanReport() {
  int n = WiFi.scanNetworks();
  printf("주변 AP %d개:\n", n);
  for (int i = 0; i < n; i++)
    printf("  %-24s ch%2d %4ddBm auth%d\n", WiFi.SSID(i).c_str(), WiFi.channel(i), WiFi.RSSI(i), WiFi.encryptionType(i));
  WiFi.scanDelete();
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  printf("WiFi: %s 연결 중", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(WIFI_PS_MAX_MODEM);
  // listen_interval 은 연결 전에만 바꿀 수 있어 connect=false 로 설정 후 직접 연결
  WiFi.begin(WIFI_SSID, WIFI_PASS, 0, nullptr, false);
  wifi_config_t cfg;
  esp_wifi_get_config(WIFI_IF_STA, &cfg);
  cfg.sta.listen_interval = LISTEN_INTERVAL;
  esp_wifi_set_config(WIFI_IF_STA, &cfg);
  esp_wifi_connect();
  for (int i = 0; i < 60 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    putchar('.'); fflush(stdout);
  }
  if (WiFi.status() == WL_CONNECTED)
    printf("\nIP %s RSSI %d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  else
  {
    printf("\n실패 (status %d, 끊김 사유 %d), 재시도 예정\n", WiFi.status(), lastDiscReason);
    WiFi.disconnect();
    scanReport();
  }
}

// /api/wait 응답 JSON 에서 "seq" 값만 뽑는다. 실패 시 -1.
long pollSeq(long known) {
  HTTPClient http;
  http.setConnectTimeout(10000);
  http.setTimeout((WAIT_SEC + 10) * 1000);   // 65000ms ≤ 65535
  // 진단: rr=부팅 원인(esp_reset_reason), nf=누적 실패, ds=마지막 WiFi 끊김 사유
  http.begin(String(SERVER_BASE) + "/api/wait?seq=" + known + "&w=" + WAIT_SEC + "&bat=" + readBatteryMv() +
             "&rssi=" + WiFi.RSSI() + "&up=" + (millis() / 1000) + "&rr=" + (int)esp_reset_reason() +
             "&nf=" + totalFails + "&ds=" + lastDiscReason);
  int code = http.GET();
  long seq = -1;
  if (code == 200) {
    String body = http.getString();
    int i = body.indexOf("\"seq\":");
    if (i >= 0) seq = body.substring(i + 6).toInt();
  } else {
    printf("wait 실패: %d\n", code);
  }
  http.end();
  return seq;
}

// /frame.bin 30000 B 를 frame 버퍼로 받는다. 서버가 보낸 seq 를 반환, 실패 시 -1.
long fetchFrame() {
  HTTPClient http;
  http.setConnectTimeout(10000);
  http.setTimeout(15000);
  http.begin(String(SERVER_BASE) + "/frame.bin");
  const char *hdrs[] = {"X-Seq"};
  http.collectHeaders(hdrs, 1);
  int code = http.GET();
  long seq = -1;
  if (code == 200 && http.getSize() == (int)sizeof(frame)) {
    WiFiClient *s = http.getStreamPtr();
    size_t got = 0;
    uint32_t t0 = millis();
    while (got < sizeof(frame) && millis() - t0 < 15000) {
      int n = s->read(frame + got, sizeof(frame) - got);
      if (n > 0) got += n; else delay(5);
    }
    if (got == sizeof(frame)) seq = http.header("X-Seq").toInt();
    else printf("frame 수신 부족: %u B\n", (unsigned)got);
  } else {
    printf("frame 실패: %d size %d\n", code, http.getSize());
  }
  http.end();
  return seq;
}

void drawFrame() {
  display.init(115200, true, 50, false);
  display.setRotation(0);
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.drawBitmap(0, 0, frame, W, H, GxEPD_BLACK);
    display.drawBitmap(0, 0, frame + PLANE, W, H, GxEPD_RED);
  } while (display.nextPage());
  display.hibernate();
}

void enablePowerSave() {
#if CONFIG_PM_ENABLE
  esp_pm_config_esp32_t pm = {};
  pm.max_freq_mhz = 80;
  pm.min_freq_mhz = 40;   // XTAL
  pm.light_sleep_enable = true;
  esp_err_t err = esp_pm_configure(&pm);
  printf("자동 라이트슬립 %s\n", err == ESP_OK ? "활성" : esp_err_to_name(err));
#else
  setCpuFrequencyMhz(80);
  puts("라이트슬립 미지원 빌드(arduino 단독) — CPU 80MHz 만 적용");
#endif
}

void setup() {
  // Arduino Serial(APB 클록)은 DFS 로 보율이 틀어지므로 IDF 콘솔(printf, REF_TICK)만 사용
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, LOW);

  SPI.end();
  SPI.begin(EPD_SCK, -1, EPD_MOSI, -1);

  WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) {
    lastDiscReason = info.wifi_sta_disconnected.reason;
  }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  printf("배터리 %d mV\n", readBatteryMv());
  enablePowerSave();

  prefs.begin("door", false);
  shownSeq = prefs.getLong("seq", -1);
  printf("\n문패 시작, 저장된 seq %ld\n", shownSeq);
}

// 통신이 안 되는 상태에 빠졌을 때 스스로 빠져나오기: 재연결 → 그래도 안 되면 재부팅
void onFail(const char *what) {
  failStreak++;
  totalFails++;
  printf("%s 실패 (연속 %d, 누적 %lu)\n", what, failStreak, (unsigned long)totalFails);
  if (failStreak % FAILS_TO_RECONNECT == 0) {
    puts("WiFi 재연결 시도");
    WiFi.disconnect();
    delay(200);
  }
}

void loop() {
  if (millis() - lastOkMs > NO_OK_RESTART_MS) {
    puts("장시간 서버 응답 없음 → 재부팅");
    delay(100);
    esp_restart();
  }
  connectWiFi();
  if (WiFi.status() != WL_CONNECTED) { onFail("WiFi"); delay(5000); return; }

  long seq = pollSeq(shownSeq);
  if (seq < 0) { onFail("wait"); delay(3000); return; }
  failStreak = 0;
  lastOkMs = millis();
  if (seq == shownSeq) return;   // 변경 없음(타임아웃) → 다시 대기

  printf("상태 변경 seq %ld → %ld, 갱신\n", shownSeq, seq);
  long got = fetchFrame();
  if (got < 0) { onFail("frame"); delay(3000); return; }
  uint32_t t0 = millis();
  drawFrame();
  printf("e-paper 갱신 완료 (%lu ms)\n", millis() - t0);
  shownSeq = got;
  prefs.putLong("seq", shownSeq);
}
