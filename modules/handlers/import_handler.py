from datetime import date, timedelta
from sqlalchemy import text as sql_text
from flask import current_app
import traceback
import time

from modules.models.base import db
from modules.utils.week_utils import (
    parse_week_parameter, 
    calculate_target_week, 
    is_week_in_past,
    get_available_weeks
)

def handle_import_fixed_trips_week(message_text):
    """處理匯入固定班次的命令

    規則調整：
    - 預設只匯入「診所」類別
    - 如需匯入其他類別（例如：東洋），需加上類別參數
      例：匯入固定班次 東洋 本週 〔可加 覆蓋〕
    """
    try:
        # 解析命令參數
        parts = message_text.strip().split()
        known_categories = {"診所", "東洋", "臨時"}
        selected_category = "診所"  # 預設只匯入診所

        # 移除命令本體
        args = parts[1:]

        # 早退：無任何參數 → 顯示周次選項（提示預設為診所）
        if not args:
            return show_available_weeks(default_category=selected_category)

        # 解析覆蓋參數（允許出現在任意位置）
        force_overwrite = False
        args_cleaned = []
        for token in args:
            if token == "覆蓋":
                force_overwrite = True
            else:
                args_cleaned.append(token)

        # 解析類別參數（允許出現在任意位置）
        args_after_category = []
        for token in args_cleaned:
            if token in known_categories and selected_category == "診所":
                selected_category = token
            else:
                args_after_category.append(token)

        # 剩餘第一個參數應為週次
        if not args_after_category:
            # 沒提供週次，顯示可用選項（保留已選類別提示）
            return show_available_weeks(default_category=selected_category)

        week_param = args_after_category[0].strip()
        # 若還有多餘未識別參數，回報錯誤
        if len(args_after_category) > 1:
            extra = " ".join(args_after_category[1:])
            return f"❌ 無法識別的參數: {extra}\n\n{show_available_weeks(default_category=selected_category)}"
        
        # 解析周次參數
        try:
            week_offset, week_name = parse_week_parameter(week_param)
        except ValueError as e:
            return f"❌ {str(e)}\n\n{show_available_weeks()}"
        
        # 計算目標周次
        today = date.today()
        week_start, dates, week_desc = calculate_target_week(today, week_offset)
        
        # 防止匯入過去時間態
        if is_week_in_past(dates, today):
            return f"❌ 不允許匯入過去時間態：{week_name} ({week_desc})\n\n{show_available_weeks()}"
        
        # 執行匯入（加上類別過濾）
        return import_week_trips(week_start, dates, week_name, week_desc, force_overwrite, selected_category)
        
    except Exception as e:
        current_app.logger.error(f"處理匯入固定班次命令失敗: {str(e)}")
        traceback.print_exc()
        return f"處理匯入固定班次命令失敗: {str(e)}"

def show_available_weeks(default_category: str = "診所"):
    """顯示可用的周次選項（預設僅匯入診所類別）"""
    try:
        weeks = get_available_weeks()
        
        result = "📅 可用的匯入周次選項：\n\n"
        
        for week_offset, name, desc in weeks:
            result += f"• 匯入固定班次 {name} ({desc})\n"
        
        result += "\n🔄 覆蓋選項：\n"
        result += "• 匯入固定班次 [周次] 覆蓋\n"

        result += "\n💡 類別規則：\n"
        result += f"• 預設僅匯入「{default_category}」類別\n"
        result += "• 如需匯入其他類別，請加入類別參數（例如：東洋）\n"

        result += "\n🧭 指令格式：\n"
        result += "• 匯入固定班次 [周次] [覆蓋]\n"
        result += "• 匯入固定班次 東洋 [周次] [覆蓋]\n"
        result += "\n範例：\n"
        result += "• 匯入固定班次 本週\n"
        result += "• 匯入固定班次 下週 覆蓋\n"
        result += "• 匯入固定班次 東洋 本週\n"
        
        return result
        
    except Exception as e:
        current_app.logger.error(f"顯示可用周次失敗: {str(e)}")
        return f"顯示可用周次失敗: {str(e)}"

def import_week_trips(week_start, dates, week_name, week_desc, force_overwrite=False, category: str = "診所"):
    """執行周次固定班次匯入 - 僅匯入指定類別（預設診所）"""
    start_time = time.time()
    
    try:
        current_app.logger.info(f"🚀 開始匯入{week_name}固定班次: {week_desc}")
        
        # 檢查是否已經匯入過（按類別分開檢查）
        check_query = """
        SELECT COUNT(*) FROM trips 
        WHERE date >= :start_date AND date <= :end_date 
          AND fixed_trip_id IS NOT NULL
          AND category = :category
        """
        
        existing_count = db.session.execute(
            sql_text(check_query), 
            {"start_date": dates[0], "end_date": dates[6], "category": category}
        ).fetchone()[0]
        
        if existing_count > 0 and not force_overwrite:
            # 提供覆蓋選項的提示
            return f"⚠️ {week_name} ({week_desc}) 的固定班次（類別：{category}）已經匯入過了（共 {existing_count} 筆）。\n\n如需覆蓋，請使用：\n🔄 匯入固定班次 {category} {week_name} 覆蓋\n\n⚠️ 注意：如選覆蓋資料，原先對班次的修改會失效"
        
        # 如果是覆蓋模式，先清除該周次的固定班次 - 優化DELETE
        if force_overwrite and existing_count > 0:
            current_app.logger.info(f"🔄 覆蓋模式：開始清除原有 {existing_count} 筆固定班次")
            
            delete_query = """
            DELETE FROM trips 
            WHERE date >= :start_date AND date <= :end_date 
              AND fixed_trip_id IS NOT NULL
              AND category = :category
            """
            delete_result = db.session.execute(
                sql_text(delete_query), 
                {"start_date": dates[0], "end_date": dates[6], "category": category}
            )
            deleted_count = delete_result.rowcount
            current_app.logger.info(f"✅ 已刪除 {deleted_count} 筆原有固定班次")
        
        # 周次選擇邏輯：
        # - 本周：在現有基礎上追加（不清空）
        # - 下周：可以清空（因為是未來規劃）
        week_offset = (week_start - date.today()).days // 7
        
        if week_offset == 0:
            # 本周：追加模式（不清空現有班次）
            current_app.logger.info("📝 本周匯入模式：追加到現有班次")
        else:
            # 未來周次：規劃模式（可以清空重新規劃）
            current_app.logger.info(f"📅 未來周次匯入模式：{week_name}")
            
            # 如果不是覆蓋模式，在匯入新班次之前，先將所有未完成的班次移到已完成班次表
            if not force_overwrite:
                current_app.logger.info("📦 正在處理未完成班次...")
                
                # 優化：添加超時控制
                timeout_start = time.time()
                try:
                    from modules.services.scheduler_service import update_completed_trips
                    update_completed_trips()
                    
                    # 檢查是否超時
                    if time.time() - timeout_start > 30:  # 30秒超時
                        current_app.logger.warning("⚠️ 處理未完成班次超時，繼續匯入流程")
                except Exception as e:
                    current_app.logger.error(f"❌ 處理未完成班次失敗: {str(e)}")
                    # 不中斷流程，繼續匯入
                
                # 優化：清空班次總覽表時添加條件，避免全表刪除
                current_app.logger.info("🗑️ 清空現有班次，準備匯入新周次")
                
                # 只刪除非固定班次，或者添加更安全的條件
                delete_query = """
                DELETE FROM trips 
                WHERE date < :start_date OR date > :end_date OR fixed_trip_id IS NULL
                """
                db.session.execute(
                    sql_text(delete_query), 
                    {"start_date": dates[0], "end_date": dates[6]}
                )
                current_app.logger.info("✅ 已清空現有班次")
        
        current_app.logger.info("📊 開始讀取固定班次資料...")
        
        # 匯入每一天的固定班次 - 優化批量處理
        total_inserted = 0
        status_counts = {'正常': 0, '請假': 0}
        batch_data = []  # 批量插入數據
        
        for day_index, import_date in enumerate(dates):
            current_app.logger.info(f"📅 處理日期: {import_date} ({day_index + 1}/7)")
            
            # 獲取星期幾（1-7，其中1是星期一）
            weekday = import_date.isoweekday()
            
            # 查詢符合當天星期且類別相符的固定班次（包含狀態和說明）
            query = """
            SELECT 
                id, route_number, departure_time, start_point, via_point, end_point, 
                base_fare, surcharge, total_fare, category, driver_id, direction, 
                status, note
            FROM fixed_schedules
            WHERE route_number LIKE :weekday_pattern
                AND (status IS NULL OR status != '停用')
                AND (category = :category)
            """
            
            fixed_trips = db.session.execute(
                sql_text(query), 
                {"weekday_pattern": f"%{weekday}%", "category": category}
            ).fetchall()
            
            current_app.logger.info(f"📦 找到 {len(fixed_trips)} 筆固定班次")
            
            # 準備批量插入數據
            for trip in fixed_trips:
                fixed_trip_id = trip[0]
                
                # 計算一年中的第幾天和第幾周
                day_of_year = import_date.timetuple().tm_yday
                _, week_number, _ = import_date.isocalendar()
                
                # 生成唯一識別碼
                unique_code = f"{fixed_trip_id}_{day_of_year}_{week_number}"
                
                # 優化：批量檢查重複（只在本周追加模式且不是覆蓋模式時）
                skip_duplicate_check = not (week_offset == 0 and not force_overwrite)
                
                if not skip_duplicate_check:
                    # 簡化重複檢查，加入批量數據時再檢查
                    pass
                
                # 處理班次狀態和請假信息
                fixed_status = trip[12] if len(trip) > 12 and trip[12] else '準備'
                fixed_note = trip[13] if len(trip) > 13 and trip[13] else None
                
                # 根據固定班次狀態設定請假相關欄位
                if fixed_status == '請假' and fixed_note:
                    passenger_leave_reason = fixed_note
                    import_extra_fare = trip[7] if trip[7] is not None else 0
                    status_counts['請假'] += 1
                else:
                    passenger_leave_reason = None
                    import_extra_fare = trip[7] if trip[7] is not None else 0
                    status_counts['正常'] += 1
                
                # 添加到批量數據
                batch_data.append({
                    "fixed_trip_id": fixed_trip_id,
                    "date": import_date,
                    "time": trip[2],
                    "start_point": trip[3],
                    "via_point": trip[4],
                    "end_point": trip[5],
                    "meter_fare": trip[6],
                    "extra_fare": import_extra_fare,
                    "category": trip[9],
                    "driver_id": trip[10],
                    "passenger_leave_reason": passenger_leave_reason,
                    "unique_code": unique_code,
                    "week_number": week_number
                })
            
            # 檢查處理時間，避免超時
            if time.time() - start_time > 45:  # 45秒超時警告
                current_app.logger.warning(f"⚠️ 處理時間較長，已處理 {day_index + 1}/7 天")
        
        # 優化：批量插入
        if batch_data:
            current_app.logger.info(f"💾 開始批量插入 {len(batch_data)} 筆資料...")
            
            batch_size = 100  # 分批處理，避免內存問題
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i + batch_size]
                
                # 如果需要檢查重複，先批量檢查
                if week_offset == 0 and not force_overwrite:
                    # 構建重複檢查的條件
                    check_conditions = []
                    check_params = {}
                    
                    for j, item in enumerate(batch):
                        check_conditions.append(f"(fixed_trip_id = :fid_{j} AND date = :date_{j})")
                        check_params[f"fid_{j}"] = item["fixed_trip_id"]
                        check_params[f"date_{j}"] = item["date"]
                    
                    if check_conditions:
                        duplicate_query = f"""
                        SELECT fixed_trip_id, date FROM trips 
                        WHERE {' OR '.join(check_conditions)}
                        """
                        
                        duplicates = db.session.execute(
                            sql_text(duplicate_query), 
                            check_params
                        ).fetchall()
                        
                        # 移除重複項
                        duplicate_set = {(row[0], row[1]) for row in duplicates}
                        batch = [item for item in batch if (item["fixed_trip_id"], item["date"]) not in duplicate_set]
                
                # 批量插入
                if batch:
                    insert_query = """
                    INSERT INTO trips 
                    (fixed_trip_id, date, time, start_point, via_point, end_point, 
                     meter_fare, extra_fare, category, driver_id, status, passenger_leave_reason, 
                     unique_code, week_number, trip_type) 
                    VALUES 
                    (:fixed_trip_id, :date, :time, :start_point, :via_point, :end_point, 
                     :meter_fare, :extra_fare, :category, :driver_id, '準備', :passenger_leave_reason, 
                     :unique_code, :week_number, 'fixed')
                    """
                    
                    db.session.execute(sql_text(insert_query), batch)
                    total_inserted += len(batch)
                    
                    current_app.logger.info(f"✅ 批量插入完成 {i + len(batch)}/{len(batch_data)}")
        
        # 提交事務
        db.session.commit()
        
        # 自動重置序列（針對匯入後可能的序列不同步問題）
        current_app.logger.info("🔧 檢查並修復資料庫序列...")
        try:
            from modules.handlers.sequence_fix_handler import check_all_sequences, fix_sequences
            results, need_fix = check_all_sequences()
            if need_fix:
                current_app.logger.info(f"發現序列問題: {need_fix}")
                fix_result = fix_sequences(need_fix)
                current_app.logger.info(f"序列修復結果: {fix_result}")
            else:
                current_app.logger.info("✅ 所有序列狀態正常")
        except Exception as seq_error:
            current_app.logger.error(f"⚠️ 序列檢查失敗: {seq_error}")
            # 不中斷主流程，繼續執行
        
        # 計算總耗時
        total_time = time.time() - start_time
        current_app.logger.info(f"🎉 成功匯入{total_inserted}筆固定班次，耗時 {total_time:.2f} 秒")
        
        # 生成匯入結果報告
        result = f"✅ 成功匯入 {week_name} ({week_desc}) {total_inserted} 筆固定班次（類別：{category}）"
        
        # 如果是覆蓋模式，添加覆蓋信息
        if force_overwrite and existing_count > 0:
            result = f"🔄 已覆蓋 {existing_count} 筆原有班次\n\n" + result
        
        # 添加狀態統計
        if status_counts['正常'] > 0 or status_counts['請假'] > 0:
            status_details = []
            if status_counts['正常'] > 0:
                status_details.append(f"正常: {status_counts['正常']}筆")
            if status_counts['請假'] > 0:
                status_details.append(f"請假: {status_counts['請假']}筆")
            
            result += f"\n\n📊 狀態統計: {', '.join(status_details)}"
        
        # 添加性能統計
        result += f"\n⏱️ 處理時間: {total_time:.2f} 秒"
        
        # 添加操作說明
        if week_offset == 0:
            result += f"\n\n💡 已追加到現有班次中，如需查看請使用「東洋班次」指令"
        else:
            result += f"\n\n💡 已清空原有班次並匯入{week_name}，現在可以開始{week_name}的派班作業"
        
        return result
        
    except Exception as e:
        # 發生錯誤時回滾事務
        db.session.rollback()
        
        # 計算錯誤發生時的耗時
        error_time = time.time() - start_time
        current_app.logger.error(f"❌ 匯入{week_name}固定班次失敗: {str(e)} (耗時 {error_time:.2f} 秒)")
        traceback.print_exc()
        
        return f"❌ 匯入{week_name}固定班次失敗: {str(e)}\n⏱️ 錯誤發生時間: {error_time:.2f} 秒\n\n💡 如問題持續，請聯繫系統管理員" 