"""
MySQL to SQLite 数据迁移脚本
"""
import pymysql
import sqlite3
import json
from datetime import datetime

# MySQL 配置
MYSQL_CONFIG = {
    "host": "192.168.10.51",
    "user": "e2e",
    "password": "E2e123!@#",
    "database": "e2etest",
    "charset": "utf8mb4"
}

# SQLite 配置
SQLITE_DB_PATH = "D:/researches/e2etest/backend/e2etest.db"


def get_mysql_connection():
    """获取MySQL连接"""
    return pymysql.connect(**MYSQL_CONFIG)


def export_mysql_data():
    """导出MySQL数据"""
    print("[INFO] Connecting to MySQL...")
    conn = get_mysql_connection()
    cursor = conn.cursor()
    
    data = {}
    
    # 导出所有表
    tables = ["test_scenarios", "test_cases", "test_reports", "test_step_results", "global_configs", "test_sessions"]
    
    for table in tables:
        print(f"[INFO] Exporting table: {table}")
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        
        # 获取列名
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        columns = [col[0] for col in cursor.fetchall()]
        
        data[table] = {
            "columns": columns,
            "rows": rows
        }
        print(f"[INFO]   - Exported {len(rows)} rows")
    
    cursor.close()
    conn.close()
    
    return data


def import_sqlite_data(data):
    """导入SQLite数据"""
    print(f"[INFO] Connecting to SQLite: {SQLITE_DB_PATH}")
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    
    tables = ["test_scenarios", "test_cases", "test_reports", "test_step_results", "global_configs", "test_sessions"]
    
    for table in tables:
        if table not in data:
            continue
            
        table_data = data[table]
        columns = table_data["columns"]
        rows = table_data["rows"]
        
        print(f"[INFO] Importing table: {table}")
        
        # 清空表
        cursor.execute(f"DELETE FROM {table}")
        
        # 插入数据
        placeholders = ",".join(["?" for _ in columns])
        insert_sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        
        for row in rows:
            # 转换特殊类型
            new_row = []
            for value in row:
                if isinstance(value, datetime):
                    new_row.append(value.isoformat())
                elif isinstance(value, (list, dict)):
                    new_row.append(json.dumps(value, ensure_ascii=False))
                else:
                    new_row.append(value)
            
            try:
                cursor.execute(insert_sql, new_row)
            except Exception as e:
                print(f"[WARN]   - Insert error: {e}")
        
        print(f"[INFO]   - Imported {len(rows)} rows")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("[OK] SQLite import complete!")


def main():
    print("=" * 60)
    print("MySQL to SQLite Migration")
    print("=" * 60)
    
    # 1. 导出MySQL数据
    print("\n[STEP 1] Exporting MySQL data...")
    data = export_mysql_data()
    
    # 2. 导入SQLite
    print("\n[STEP 2] Importing to SQLite...")
    import_sqlite_data(data)
    
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
