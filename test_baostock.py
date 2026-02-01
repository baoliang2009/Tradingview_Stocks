import baostock as bs
from datetime import datetime, timedelta

lg = bs.login()

today = datetime.now()
print(f"当前日期: {today.strftime('%Y-%m-%d')}")

# 尝试最近几个工作日
for days_back in range(10):
    test_date = today - timedelta(days=days_back)
    date_str = test_date.strftime("%Y-%m-%d")
    
    print(f"\n尝试查询日期: {date_str}")
    rs = bs.query_all_stock(day=date_str)
    
    print(f"错误码: {rs.error_code}")
    print(f"错误信息: {rs.error_msg}")
    
    if rs.error_code == '0':
        count = 0
        while rs.next():
            row = rs.get_row_data()
            print(f"第{count}行: {row}")
            count += 1
            if count >= 5:
                break
        
        print(f"获取到: {count} 条数据")
        if count > 0:
            break

bs.logout()
