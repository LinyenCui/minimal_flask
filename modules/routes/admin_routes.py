from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from modules.models.base import db
from sqlalchemy import text
import logging

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/database-tools')
def database_tools():
    """資料庫工具頁面"""
    return render_template('admin/database_tools.html')

@admin_bp.route('/fix-sequences', methods=['POST'])
def fix_sequences():
    """修復資料庫序列API"""
    try:
        action = request.json.get('action', 'all')
        results = []
        
        if action == 'completed_trips' or action == 'all':
            result = fix_table_sequence('completed_trips', 'completed_trips_id_seq', 'id')
            results.append(result)
        
        if action == 'trips' or action == 'all':
            result = fix_table_sequence('trips', 'trips_trip_id_seq', 'trip_id')
            results.append(result)
            
        if action == 'persons' or action == 'all':
            result = fix_table_sequence('persons', 'persons_id_seq', 'id')
            results.append(result)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '序列修復完成',
            'results': results
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"序列修復失敗: {e}")
        return jsonify({
            'success': False,
            'message': f'修復失敗: {str(e)}'
        }), 500

def fix_table_sequence(table_name, sequence_name, id_column):
    """修復單一表格的序列"""
    try:
        # 獲取最大ID
        max_id_query = f"SELECT COALESCE(MAX({id_column}), 0) FROM {table_name};"
        max_result = db.session.execute(text(max_id_query)).fetchone()
        max_id = max_result[0] if max_result else 0
        
        # 獲取當前序列值
        seq_query = f"SELECT last_value FROM {sequence_name};"
        seq_result = db.session.execute(text(seq_query)).fetchone()
        current_seq = seq_result[0] if seq_result else 0
        
        result = {
            'table': table_name,
            'max_id': max_id,
            'old_sequence': current_seq,
            'status': 'ok'
        }
        
        if current_seq < max_id:  # 修正邏輯：只有當序列值小於最大ID時才需要修復
            next_val = max_id + 1
            fix_query = f"SELECT setval('{sequence_name}', {next_val}, false);"
            db.session.execute(text(fix_query))
            result['new_sequence'] = next_val
            result['status'] = 'fixed'
        else:
            result['new_sequence'] = current_seq
            result['status'] = 'ok'
        
        return result
        
    except Exception as e:
        return {
            'table': table_name,
            'error': str(e),
            'status': 'error'
        }

@admin_bp.route('/check-sequences')
def check_sequences():
    """檢查所有序列狀態"""
    try:
        tables = [
            ('completed_trips', 'completed_trips_id_seq', 'id'),
            ('trips', 'trips_trip_id_seq', 'trip_id'),
            ('persons', 'persons_id_seq', 'id')
        ]
        
        results = []
        for table_name, seq_name, id_col in tables:
            try:
                # 獲取最大ID
                max_id_query = f"SELECT COALESCE(MAX({id_col}), 0) FROM {table_name};"
                max_result = db.session.execute(text(max_id_query)).fetchone()
                max_id = max_result[0] if max_result else 0
                
                # 獲取序列值
                seq_query = f"SELECT last_value FROM {seq_name};"
                seq_result = db.session.execute(text(seq_query)).fetchone()
                current_seq = seq_result[0] if seq_result else 0
                
                results.append({
                    'table': table_name,
                    'max_id': max_id,
                    'sequence_value': current_seq,
                    'needs_fix': current_seq < max_id,  # 修正邏輯：只有當序列值小於最大ID時才需要修復
                    'status': 'warning' if current_seq < max_id else 'ok'
                })
                
            except Exception as e:
                results.append({
                    'table': table_name,
                    'error': str(e),
                    'status': 'error'
                })
        
        return jsonify({
            'success': True,
            'sequences': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500 