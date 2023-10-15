import logging
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map_pydantic import (
    AvellanedaMarketMakingConfigMap,
    InfiniteModel,
    SingleOrderLevelModel,
    IgnoreHangingOrdersModel
)
from hummingbot.core.clock import Clock
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.strategy.avellaneda_market_making import AvellanedaMarketMakingStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from decimal import Decimal
from typing import List, Tuple

class HummingBotAvellaneda(ScriptStrategyBase):
    c_map = ClientConfigAdapter(
        AvellanedaMarketMakingConfigMap(
            exchange='okx',
            market='ETH-USDT',
            execution_timeframe_mode=InfiniteModel,
            order_amount=Decimal('1'),
            order_optimization_enabled=True,
            risk_factor=Decimal("1"),
            order_amount_shape_factor=Decimal("0"),
            min_spread=Decimal("0"),
            order_refresh_time=0.0001,
            max_order_age=1800,
            order_refresh_tolerance_pct=Decimal("0"),
            filled_order_delay=60,
            inventory_target_base_pct=Decimal("50"),
            add_transaction_costs=False,
            volatility_buffer_size=200,
            trading_intensity_buffer_size=200,
            order_levels_mode=SingleOrderLevelModel.construct(),
            order_override=None,
            hanging_orders_mode=IgnoreHangingOrdersModel(),
            should_wait_order_cancel_confirmation=True
        )
    )

    exchange = c_map.exchange
    raw_trading_pair = c_map.market

    trading_pair: str = raw_trading_pair

    # utility of HummingbotApplication won't work IMHO
    maker_assets: Tuple[str, str] = HummingbotApplication._initialize_market_assets(
        exchange, 
        [trading_pair]
    )[0]
    market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
    HummingbotApplication._initialize_markets(market_names)
    maker_data = [HummingbotApplication.markets[exchange], trading_pair] + list(maker_assets)
    market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

    strategy = AvellanedaMarketMakingStrategy()
    strategy.init_params(
        config_map=c_map,
        market_info=MarketTradingPairTuple(*maker_data),
        hb_app_notification=True
    )
    startBalance = 0

    
    def start(self):
        # clock + current timestamp
        self.strategy.start(self.current_timestamp)


    def on_tick(self):
        self.calculate_pnl()
        # timestamp
        self.strategy.process_tick()


    def get_pair_balance(self) -> float:
        price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
        balance_df = self.get_balance_df()
        base_balances = {}
        base_currencies = [self.trading_pair[:self.trading_pair.find("-")], self.trading_pair[self.trading_pair.find("-") + 1:]]
        exchange_balance_df = balance_df.loc[balance_df["Exchange"] == self.exchange]
        for _, row in exchange_balance_df.iterrows():
            asset_name = row["Asset"]
            if asset_name in base_currencies:
                total_balance = Decimal(row["Total Balance"])
                available_balance = Decimal(row["Available Balance"])
                base_balances[asset_name] = (total_balance, available_balance)
        pair_balance = base_balances[base_currencies[0]][0] * price + base_balances[base_currencies[1]][0]
        return pair_balance
    

    def calculate_pnl(self) -> float:
        current_balance = self.get_pair_balance()
        diff = current_balance - self.startBalance
        msg = (f"Current PnL: {diff}")
        self.logger().notify(msg)
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
        msg = (f"Current spread: {self.bid_spread}")
        self.logger().notify(msg)
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)
        return diff
