//+------------------------------------------------------------------+
//|                                          VolatilitySqueezeEA.mq5  |
//|   Volatility Squeeze (บท 4) : ATR + Bollinger Band Width บีบตัว   |
//|   -> รอ Breakout พร้อมการขยายตัวของความผันผวน                     |
//|                                                                  |
//|   แนวคิด: เมื่อ BB Width ต่ำผิดปกติ (บีบตัว) + ATR ต่ำ            |
//|   แล้วราคาทะลุกรอบพร้อม ATR เริ่มขยาย = สัญญาณ Breakout           |
//|                                                                  |
//|   *** เพื่อการศึกษา ต้อง backtest + ปรับค่าก่อนใช้เงินจริง ***    |
//+------------------------------------------------------------------+
#property copyright "Squeeze EA Project"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//--- Inputs : Bollinger / ATR
input int      BB_Period        = 20;      // Bollinger period
input double   BB_Deviation     = 2.0;     // Bollinger deviation
input int      ATR_Period       = 14;      // ATR period
input int      SqueezeLookback  = 50;      // หน้าต่างวัดว่า "บีบตัว" แค่ไหน
input double   SqueezeFactor    = 0.80;    // width < ค่าเฉลี่ย*factor = บีบตัว (ยิ่งต่ำยิ่งเข้ม)

//--- Inputs : Risk / Exit
input double   RiskPercent      = 1.0;     // เสี่ยงต่อไม้ (% ของ balance)
input double   SL_ATR_Mult      = 1.5;     // Stop Loss = ATR * ค่านี้
input double   TP_RR            = 2.0;     // Take Profit = ความเสี่ยง * RR
input bool     UseTrailing      = true;    // ใช้ ATR trailing stop
input double   Trail_ATR_Mult   = 2.0;     // ระยะ trailing = ATR * ค่านี้

//--- Inputs : ทั่วไป
input int      MagicNumber      = 480024;  // รหัสระบุไม้ของ EA นี้
input int      MaxPositions     = 1;       // จำนวนไม้สูงสุดพร้อมกัน

//--- handles
int    hBB, hATR;
double bbUpper[], bbLower[], bbMiddle[], atrBuf[];
datetime lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   hBB  = iBands(_Symbol, _Period, BB_Period, 0, BB_Deviation, PRICE_CLOSE);
   hATR = iATR(_Symbol, _Period, ATR_Period);
   if(hBB == INVALID_HANDLE || hATR == INVALID_HANDLE)
   {
      Print("สร้าง indicator ไม่สำเร็จ");
      return(INIT_FAILED);
   }
   trade.SetExpertMagicNumber(MagicNumber);
   ArraySetAsSeries(bbUpper, true);
   ArraySetAsSeries(bbLower, true);
   ArraySetAsSeries(bbMiddle, true);
   ArraySetAsSeries(atrBuf, true);
   Print("VolatilitySqueezeEA เริ่มทำงานบน ", _Symbol, " TF=", EnumToString(_Period));
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(hBB  != INVALID_HANDLE) IndicatorRelease(hBB);
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(UseTrailing) ManageTrailing();

   // ทำงานเฉพาะเมื่อเกิดแท่งใหม่ (ตัดสินใจบนแท่งที่ปิดแล้ว)
   datetime t = (datetime)SeriesInfoInteger(_Symbol, _Period, SERIES_LASTBAR_DATE);
   if(t == lastBarTime) return;
   lastBarTime = t;

   int need = MathMax(SqueezeLookback + 3, BB_Period + 3);
   if(CopyBuffer(hBB, 0, 0, need, bbMiddle) < need) return;
   if(CopyBuffer(hBB, 1, 0, need, bbUpper)  < need) return;
   if(CopyBuffer(hBB, 2, 0, need, bbLower)  < need) return;
   if(CopyBuffer(hATR, 0, 0, need, atrBuf)  < need) return;

   // --- BB width (%) เทียบเส้นกลาง ---
   double widthNow = BBWidth(1);                 // แท่งที่ปิดล่าสุด
   double avgWidth = 0;
   for(int i = 2; i <= SqueezeLookback + 1; i++) avgWidth += BBWidth(i);
   avgWidth /= SqueezeLookback;

   bool wasSqueeze = (BBWidth(2) < avgWidth * SqueezeFactor); // แท่งก่อนหน้าบีบตัว
   bool expanding  = (atrBuf[1] > atrBuf[2]);                 // ATR เริ่มขยาย

   double close1 = iClose(_Symbol, _Period, 1);

   bool breakoutUp   = (close1 > bbUpper[1]);
   bool breakoutDown = (close1 < bbLower[1]);

   if(CountMyPositions() >= MaxPositions) return;

   if(wasSqueeze && expanding && breakoutUp)
      OpenTrade(ORDER_TYPE_BUY);
   else if(wasSqueeze && expanding && breakoutDown)
      OpenTrade(ORDER_TYPE_SELL);
}

//+------------------------------------------------------------------+
double BBWidth(int shift)
{
   if(bbMiddle[shift] == 0) return 0;
   return (bbUpper[shift] - bbLower[shift]) / bbMiddle[shift] * 100.0;
}

//+------------------------------------------------------------------+
void OpenTrade(ENUM_ORDER_TYPE type)
{
   double atr   = atrBuf[1];
   double price = (type == ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                           : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double slDist = atr * SL_ATR_Mult;
   if(slDist <= 0) return;

   double sl = (type == ORDER_TYPE_BUY) ? price - slDist : price + slDist;
   double tp = (type == ORDER_TYPE_BUY) ? price + slDist * TP_RR : price - slDist * TP_RR;
   double lot = CalcLot(slDist);
   if(lot <= 0) return;

   if(type == ORDER_TYPE_BUY)
      trade.Buy(lot, _Symbol, price, sl, tp, "Squeeze breakout UP");
   else
      trade.Sell(lot, _Symbol, price, sl, tp, "Squeeze breakout DOWN");
}

//+------------------------------------------------------------------+
double CalcLot(double slDistPrice)
{
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * RiskPercent / 100.0;
   double tickVal   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickVal <= 0) return 0;

   double lossPerLot = (slDistPrice / tickSize) * tickVal;
   if(lossPerLot <= 0) return 0;

   double lot = riskMoney / lossPerLot;

   // ปัดตาม step + จำกัด min/max
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lot = MathFloor(lot / step) * step;
   lot = MathMax(minL, MathMin(maxL, lot));
   return lot;
}

//+------------------------------------------------------------------+
void ManageTrailing()
{
   if(CopyBuffer(hATR, 0, 0, 2, atrBuf) < 2) return;
   double atr = atrBuf[0];
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      long   type  = PositionGetInteger(POSITION_TYPE);
      double open  = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL = PositionGetDouble(POSITION_SL);
      double curTP = PositionGetDouble(POSITION_TP);
      double trail = atr * Trail_ATR_Mult;

      if(type == POSITION_TYPE_BUY)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double newSL = bid - trail;
         if(newSL > open && (curSL == 0 || newSL > curSL))
            trade.PositionModify(ticket, newSL, curTP);
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double newSL = ask + trail;
         if(newSL < open && (curSL == 0 || newSL < curSL))
            trade.PositionModify(ticket, newSL, curTP);
      }
   }
}

//+------------------------------------------------------------------+
int CountMyPositions()
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) == MagicNumber &&
         PositionGetString(POSITION_SYMBOL) == _Symbol)
         c++;
   }
   return c;
}
//+------------------------------------------------------------------+
