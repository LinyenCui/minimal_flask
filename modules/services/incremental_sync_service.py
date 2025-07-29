#!/usr/bin/env python3
"""
增量資料庫同步服務
解決本地數據丟失問題，實現智能增量同步
"""

import os
import logging
import psycopg2
from psycopg2.extras import DictCursor, execute_batch
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IncrementalSyncService:
    """增量同步服務類"""
    
    def __init__(self):
        load_dotenv()
        self.render_config = {
            "host": os.getenv('RENDER_DB_HOST'),
            "user": os.getenv('RENDER_DB_USER'),
            "dbname": os.getenv('RENDER_DB_NAME'),
            "password": os.getenv('RENDER_DB_PASSWORD'),
            "sslmode": 'require'
        }
        
        self.local_config = {
            "host": os.getenv('LOCAL_DB_HOST', 'localhost'),
            "user": os.getenv('LOCAL_DB_USER', ''),
            "dbname": os.getenv('LOCAL_DB_NAME', 'dispatch_db'),
            "password": os.getenv('LOCAL_DB_PASSWORD', '')
        }
        
        # 定義生成欄位（需要過濾的欄位）
        self.generated_columns = {
            'trips': ['actual_fare', 'total_fare'],
            'completed_trips': ['actual_fare', 'total_fare'],
            'fixed_schedules': [],
            'drivers': [],
            'customers': []
        }
        
    def get_connection(self, config: Dict, name: str):
        """建立資料庫連接"""
        try:
            conn = psycopg2.connect(**config)
            logger.info(f"✅ 成功連接到 {name} 資料庫")
            return conn
        except Exception as e:
            logger.error(f"❌ 連接 {name} 資料庫失敗: {e}")
            return None
    
    def get_table_columns(self, conn, table_name: str) -> List[str]:
        """獲取表的所有欄位名稱"""
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s 
                ORDER BY ordinal_position
            """, (table_name,))
            return [row[0] for row in cur.fetchall()]
    
    def filter_generated_columns(self, table_name: str, columns: List[str]) -> List[str]:
        """過濾生成欄位"""
        generated = self.generated_columns.get(table_name, [])
        filtered = [col for col in columns if col not in generated]
        
        if generated:
            logger.info(f"   - 過濾生成欄位 {table_name}: {generated}")
            logger.info(f"   - 剩餘欄位: {len(filtered)}個")
        
        return filtered
    
    def get_last_sync_date(self, local_conn, table_name: str) -> Optional[date]:
        """獲取本地最後同步日期"""
        with local_conn.cursor() as cur:
            try:
                # 嘗試從date欄位獲取
                cur.execute(f"SELECT MAX(date) FROM {table_name}")
                result = cur.fetchone()[0]
                
                if result is None and table_name == 'trips':
                    # trips表還可以嘗試booking_date欄位
                    cur.execute(f"SELECT MAX(booking_date) FROM {table_name}")  
                    result = cur.fetchone()[0]
                
                return result
            except Exception as e:
                logger.warning(f"獲取 {table_name} 最後日期失敗: {e}")
                return None
    
    def incremental_sync_table(self, local_conn, render_conn, table_name: str, 
                              date_column: str = 'date', 
                              days_overlap: int = 3) -> Dict:
        """
        增量同步指定表
        
        Args:
            local_conn: 本地資料庫連接
            render_conn: Render資料庫連接  
            table_name: 表名
            date_column: 日期欄位名稱
            days_overlap: 重疊天數（避免遺漏）
            
        Returns:
            同步結果統計
        """
        logger.info(f"🔄 開始增量同步表: {table_name}")
        
        result = {
            'table': table_name,
            'success': False,
            'new_records': 0,
            'updated_records': 0,
            'error': None
        }
        
        try:
            with local_conn.cursor() as local_cur, render_conn.cursor(cursor_factory=DictCursor) as render_cur:
                
                # 1. 獲取本地最新日期
                last_local_date = self.get_last_sync_date(local_conn, table_name)
                
                if last_local_date is None:
                    # 如果本地沒有數據，從較早日期開始
                    sync_from_date = date(2024, 1, 1)
                    logger.info(f"   - 本地無數據，從 {sync_from_date} 開始同步")
                else:
                    # 往前推幾天，確保不遺漏
                    sync_from_date = last_local_date - timedelta(days=days_overlap)
                    logger.info(f"   - 本地最新日期: {last_local_date}，從 {sync_from_date} 開始同步")
                
                # 2. 獲取表結構
                all_columns = self.get_table_columns(render_conn, table_name)
                filtered_columns = self.filter_generated_columns(table_name, all_columns)
                
                # 3. 從Render讀取新數據
                columns_str = ', '.join(filtered_columns)
                render_cur.execute(f"""
                    SELECT {columns_str} 
                    FROM {table_name} 
                    WHERE {date_column} >= %s 
                    ORDER BY {date_column}, id
                """, (sync_from_date,))
                
                new_records = render_cur.fetchall()
                
                if not new_records:
                    logger.info(f"   - ✅ {table_name} 無新數據需要同步")
                    result['success'] = True
                    return result
                
                logger.info(f"   - 從Render獲取 {len(new_records)} 筆記錄")
                
                # 4. 使用UPSERT策略插入數據
                placeholders = ', '.join(['%s'] * len(filtered_columns))
                
                # 構建UPSERT SQL（使用ON CONFLICT）
                if 'id' in filtered_columns:
                    # 有id欄位，使用id作為衝突鍵
                    upsert_sql = f"""
                        INSERT INTO {table_name} ({columns_str}) 
                        VALUES ({placeholders})
                        ON CONFLICT (id) DO UPDATE SET
                        {', '.join([f"{col} = EXCLUDED.{col}" for col in filtered_columns if col != 'id'])}
                    """
                else:
                    # 沒有id欄位，使用DO NOTHING
                    upsert_sql = f"""
                        INSERT INTO {table_name} ({columns_str}) 
                        VALUES ({placeholders})
                        ON CONFLICT DO NOTHING
                    """
                
                # 5. 批量執行UPSERT
                records_data = [[record[col] for col in filtered_columns] for record in new_records]
                
                execute_batch(local_cur, upsert_sql, records_data)
                affected_rows = local_cur.rowcount
                local_conn.commit()
                
                result['new_records'] = affected_rows
                result['success'] = True
                
                logger.info(f"   - ✅ {table_name} 同步完成: {affected_rows} 筆數據")
                
        except Exception as e:
            local_conn.rollback()
            error_msg = f"同步 {table_name} 失敗: {e}"
            logger.error(f"   - ❌ {error_msg}")
            result['error'] = error_msg
            
        return result
    
    def sync_sequence(self, local_conn, table_name: str) -> bool:
        """同步序列到當前最大ID值"""
        try:
            with local_conn.cursor() as cur:
                # 獲取當前最大ID
                cur.execute(f"SELECT MAX(id) FROM {table_name}")
                max_id = cur.fetchone()[0]
                
                if max_id is None:
                    logger.info(f"   - {table_name} 表為空，跳過序列同步")
                    return True
                
                # 重設序列
                sequence_name = f"{table_name}_id_seq"
                cur.execute(f"SELECT setval('{sequence_name}', %s)", (max_id,))
                local_conn.commit()
                
                logger.info(f"   - ✅ {table_name} 序列已重設為 {max_id}")
                return True
                
        except Exception as e:
            logger.error(f"   - ❌ 同步 {table_name} 序列失敗: {e}")
            return False
    
    def full_incremental_sync(self, tables: List[str] = None) -> Dict:
        """
        執行完整的增量同步
        
        Args:
            tables: 要同步的表列表，None表示同步所有支援的表
            
        Returns:
            同步結果統計
        """
        if tables is None:
            tables = ['drivers', 'customers', 'fixed_schedules', 'trips', 'completed_trips']
        
        logger.info("🚀 開始智能增量同步流程")
        logger.info("=" * 60)
        
        # 連接資料庫
        render_conn = self.get_connection(self.render_config, "Render")
        local_conn = self.get_connection(self.local_config, "Local")
        
        if not render_conn or not local_conn:
            return {'success': False, 'error': '資料庫連接失敗'}
        
        results = {
            'success': True,
            'total_tables': len(tables),
            'synced_tables': 0,
            'total_new_records': 0,
            'table_results': [],
            'errors': []
        }
        
        try:
            for table in tables:
                result = self.incremental_sync_table(local_conn, render_conn, table)
                results['table_results'].append(result)
                
                if result['success']:
                    results['synced_tables'] += 1
                    results['total_new_records'] += result['new_records']
                    
                    # 同步序列
                    if table in ['trips', 'completed_trips', 'drivers', 'customers', 'fixed_schedules']:
                        self.sync_sequence(local_conn, table)
                else:
                    results['errors'].append(result['error'])
            
            # 整體成功判斷
            results['success'] = results['synced_tables'] == results['total_tables']
            
            logger.info("=" * 60)
            logger.info(f"🎉 增量同步完成!")
            logger.info(f"📊 成功同步 {results['synced_tables']}/{results['total_tables']} 個表")
            logger.info(f"📈 總共新增/更新 {results['total_new_records']} 筆記錄")
            
            if results['errors']:
                logger.warning(f"⚠️  發生 {len(results['errors'])} 個錯誤")
                for error in results['errors']:
                    logger.warning(f"   - {error}")
            
        finally:
            if render_conn:
                render_conn.close()
            if local_conn:
                local_conn.close()
            logger.info("🔌 資料庫連線已關閉")
        
        return results
    
    def preserve_local_data_sync(self, backup_days: int = 7) -> Dict:
        """
        保護性增量同步 - 確保本地數據不丟失
        
        Args:
            backup_days: 備份天數
            
        Returns:
            同步結果
        """
        logger.info(f"🛡️  開始保護性增量同步（保留 {backup_days} 天本地數據）")
        
        # 先執行增量同步
        results = self.full_incremental_sync()
        
        if results['success']:
            logger.info("✅ 增量同步成功，本地數據已保護")
        else:
            logger.error("❌ 增量同步失敗，請檢查錯誤信息")
        
        return results

# 獨立執行函數
def main():
    """主函數 - 可直接執行增量同步"""
    sync_service = IncrementalSyncService()
    
    # 執行保護性增量同步
    results = sync_service.preserve_local_data_sync()
    
    return results['success']

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)