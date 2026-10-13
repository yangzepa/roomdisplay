// WeAct 4.2" 3색 e-paper + TTGO T-Display 동작 확인 스케치 (확정 결선)
#include <GxEPD2_3C.h>
#include <SPI.h>

#define EPD_SCK   25
#define EPD_MOSI  26
#define EPD_CS    27
#define EPD_DC    33
#define EPD_RST   32
#define EPD_BUSY  37
#define LCD_BL     4   // 온보드 LCD 백라이트

GxEPD2_3C<GxEPD2_420c_GDEY042Z98, GxEPD2_420c_GDEY042Z98::HEIGHT>
  display(GxEPD2_420c_GDEY042Z98(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

void setup() {
  Serial.begin(115200);
  pinMode(LCD_BL, OUTPUT);
  digitalWrite(LCD_BL, LOW);

  SPI.end();
  SPI.begin(EPD_SCK, -1, EPD_MOSI, -1);
  display.init(115200, true, 50, false);
  display.setRotation(0);          // 400x300 가로
  display.setTextWrap(false);

  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.drawRect(5, 5, 390, 290, GxEPD_BLACK);
    display.fillRect(12, 12, 376, 42, GxEPD_RED);
    display.setTextSize(2);
    display.setTextColor(GxEPD_WHITE);
    display.setCursor(30, 25);  display.print("3-COLOR E-PAPER ONLINE");
    display.setTextColor(GxEPD_BLACK);
    display.setCursor(25, 80);  display.print("SCK25 MOSI26 CS27");
    display.setCursor(25, 110); display.print("DC33 RST32 BUSY37");
  } while (display.nextPage());

  display.hibernate();
  Serial.println("done");
}

void loop() {}
