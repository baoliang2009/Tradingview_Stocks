"""
直接测试止损逻辑
创建一个明确会触发止损的场景
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 模拟回测引擎的核心止损逻辑
def test_stop_loss_logic():
    """直接测试止损计算逻辑"""
    print("=" * 80)
    print("止损逻辑单元测试")
    print("=" * 80)
    
    # 场景1: 买入后价格下跌15%，应该在-10%处止损
    print("\n场景1: 买入100元，然后价格下跌到85元")
    print("-" * 80)
    
    buy_price = 100.0
    commission = 0.0003
    slippage = 0.001
    stop_loss_pct = 0.10
    
    # 买入成本
    buy_cost = buy_price * (1 + slippage + commission)
    print(f"买入价格: {buy_price:.2f}")
    print(f"买入成本(含手续费+滑点): {buy_cost:.2f}")
    
    # 模拟每天的价格
    daily_prices = [100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 80]
    
    stop_triggered = False
    stop_day = None
    stop_price = None
    
    for day, price in enumerate(daily_prices):
        current_return = (price - buy_cost) / buy_cost
        print(f"第{day}天: 价格={price:.2f}, 收益率={current_return*100:.2f}%", end="")
        
        if current_return <= -stop_loss_pct:
            print(f" ← 触发止损!")
            stop_triggered = True
            stop_day = day
            stop_price = price
            break
        else:
            print()
    
    if stop_triggered:
        sell_net = stop_price * (1 - slippage - commission)
        final_return = (sell_net - buy_cost) / buy_cost * 100
        print(f"\n止损结果:")
        print(f"  止损触发日: 第{stop_day}天")
        print(f"  止损价格: {stop_price:.2f}")
        print(f"  卖出净值: {sell_net:.2f}")
        print(f"  最终收益率: {final_return:.2f}%")
        print(f"  ✓ 止损逻辑正常工作！")
    else:
        print(f"\n⚠ 止损未触发")
    
    # 场景2: 买入后价格下跌5%，不应触发止损
    print("\n\n场景2: 买入100元，价格小幅下跌到96元（不应触发止损）")
    print("-" * 80)
    
    buy_cost = buy_price * (1 + slippage + commission)
    daily_prices = [100, 99, 98, 97, 96, 95.5, 96, 97]
    
    stop_triggered = False
    
    for day, price in enumerate(daily_prices):
        current_return = (price - buy_cost) / buy_cost
        print(f"第{day}天: 价格={price:.2f}, 收益率={current_return*100:.2f}%", end="")
        
        if current_return <= -stop_loss_pct:
            print(f" ← 触发止损!")
            stop_triggered = True
            break
        else:
            print()
    
    if not stop_triggered:
        print(f"\n✓ 止损未触发（符合预期，因为跌幅<10%）")
    else:
        print(f"\n✗ 错误：不应该触发止损")
    
    # 场景3: 准确测试边界条件 (-9.9% vs -10.1%)
    print("\n\n场景3: 边界测试")
    print("-" * 80)
    
    buy_cost = buy_price * (1 + slippage + commission)
    
    # 测试-9.9%
    test_price_1 = buy_cost * (1 - 0.099)
    return_1 = (test_price_1 - buy_cost) / buy_cost
    print(f"价格={test_price_1:.4f}, 收益率={return_1*100:.2f}%, ", end="")
    print(f"{'不触发止损' if return_1 > -stop_loss_pct else '触发止损'}")
    
    # 测试-10.0%
    test_price_2 = buy_cost * (1 - 0.100)
    return_2 = (test_price_2 - buy_cost) / buy_cost
    print(f"价格={test_price_2:.4f}, 收益率={return_2*100:.2f}%, ", end="")
    print(f"{'不触发止损' if return_2 > -stop_loss_pct else '触发止损'}")
    
    # 测试-10.1%
    test_price_3 = buy_cost * (1 - 0.101)
    return_3 = (test_price_3 - buy_cost) / buy_cost
    print(f"价格={test_price_3:.4f}, 收益率={return_3*100:.2f}%, ", end="")
    print(f"{'不触发止损' if return_3 > -stop_loss_pct else '触发止损'}")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    test_stop_loss_logic()
