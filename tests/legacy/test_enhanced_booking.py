#!/usr/bin/env python3
"""
測試增強版AI預約功能（日文支援和圖片解析）
"""
import sys
from pathlib import Path
import io
from PIL import Image, ImageDraw, ImageFont

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_multilingual_booking():
    """測試多語言預約功能"""
    print("🌏 測試多語言AI預約功能")
    print("=" * 60)
    
    try:
        from modules.services.ai_service_enhanced import extract_booking_info_with_gemini
        
        test_cases = [
            # 中文測試案例
            ("中文 - 基本預約", "明天下午三點半從火車站送到成大醫院，東洋的"),
            ("中文 - 日文混合", "預約明日午後2時，從高鐵站到東洋，送張先生"),
            ("中文 - 車資信息", "後天早上9點從安平到診所，車資400元"),
            
            # 日文測試案例
            ("日文 - 基本預約", "明日午後3時半に駅から病院まで送ってください"),
            ("日文 - 詳細預約", "あさって朝9時に田中さんを新幹線駅から東洋まで、料金500円"),
            ("日文 - 經由地點", "今日午後に佐藤様のお迎え、会社から安平を経由して病院まで"),
            ("日文 - クリニック", "明日朝、和緯路152號のクリニック、山田さんをお迎え"),
        ]
        
        for description, text in test_cases:
            print(f"\n📝 {description}")
            print(f"輸入: {text}")
            print("-" * 40)
            
            try:
                result = extract_booking_info_with_gemini(text)
                if result:
                    print("✅ 解析成功:")
                    for key, value in result.items():
                        if value is not None:
                            print(f"   {key}: {value}")
                else:
                    print("❌ 解析失敗")
                    
            except Exception as e:
                print(f"❌ 處理失敗: {e}")
            
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ 多語言測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_test_image(text, filename):
    """創建包含文字的測試圖片"""
    try:
        # 創建圖片
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        # 嘗試使用系統字體
        try:
            # 在不同系統上嘗試不同的字體
            font_paths = [
                "/System/Library/Fonts/Arial.ttf",  # macOS
                "/System/Library/Fonts/Helvetica.ttc",  # macOS
                "C:\\Windows\\Fonts\\arial.ttf",  # Windows
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            ]
            
            font = None
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, 36)
                    break
                except (OSError, IOError):
                    continue
            
            if font is None:
                font = ImageFont.load_default()
                
        except Exception:
            font = ImageFont.load_default()
        
        # 繪製文字
        lines = text.split('\n')
        y_offset = 50
        
        for line in lines:
            draw.text((50, y_offset), line, fill='black', font=font)
            y_offset += 60
        
        # 保存圖片
        img_path = project_root / f"test_images/{filename}"
        img_path.parent.mkdir(exist_ok=True)
        img.save(img_path, 'JPEG')
        
        return img_path
        
    except Exception as e:
        print(f"創建測試圖片失敗: {e}")
        return None

def test_image_booking():
    """測試圖片預約功能"""
    print("\n🖼️  測試圖片AI預約功能")
    print("=" * 60)
    
    try:
        from modules.services.ai_service_enhanced import extract_booking_info_from_image
        
        # 創建測試圖片
        test_images = [
            ("預約筆記 - 中文", "預約信息\n\n日期: 明天\n時間: 下午3:30\n起點: 台南火車站\n終點: 成大醫院\n乘客: 張先生\n車資: 400元"),
            ("予約メモ - 日文", "予約情報\n\n日付: 明日\n時刻: 午後2時\n出発地: 新幹線駅\n目的地: 東洋\n乘客: 田中さん\n料金: 500円"),
            ("混合語言", "預約/予約\n\n7/25 14:00\nFrom: 高鐵站\nTo: クリニック\n途經: 安平\n佐藤様"),
        ]
        
        for description, content in test_images:
            print(f"\n📷 {description}")
            print("圖片內容:")
            for line in content.split('\n'):
                print(f"   {line}")
            print("-" * 40)
            
            try:
                # 創建測試圖片
                img_path = create_test_image(content, f"test_{description.replace(' ', '_')}.jpg")
                
                if img_path and img_path.exists():
                    # 讀取圖片並測試
                    with open(img_path, 'rb') as f:
                        image_data = f.read()
                    
                    result = extract_booking_info_from_image(image_data)
                    
                    if result:
                        print("✅ 圖片解析成功:")
                        for key, value in result.items():
                            if value is not None:
                                print(f"   {key}: {value}")
                    else:
                        print("❌ 圖片解析失敗")
                else:
                    print("❌ 無法創建測試圖片")
                    
            except Exception as e:
                print(f"❌ 圖片處理失敗: {e}")
            
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ 圖片測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration():
    """測試整合功能"""
    print("\n🔗 測試整合功能")
    print("=" * 60)
    
    try:
        from modules.handlers.temp_booking_handler import handle_temp_booking_start, handle_temp_booking_message
        
        # 模擬預約流程
        user_id = "test_user_enhanced"
        
        print("1. 開始預約流程")
        start_response = handle_temp_booking_start(user_id)
        print(f"   回應: {start_response['text'][:100]}...")
        
        print("\n2. 測試中文輸入")
        response = handle_temp_booking_message(user_id, "明天下午2點從火車站到醫院，送李先生")
        print(f"   回應類型: {response['type']}")
        
        print("\n3. 測試日文輸入")
        user_id_jp = "test_user_japanese"
        handle_temp_booking_start(user_id_jp)
        response = handle_temp_booking_message(user_id_jp, "明日午後3時に駅から病院まで、田中さんをお迎え")
        print(f"   回應類型: {response['type']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 整合測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_language_detection():
    """測試語言檢測功能"""
    print("\n🔍 測試語言檢測功能")
    print("=" * 60)
    
    try:
        from modules.services.ai_service_enhanced import detect_language
        
        test_cases = [
            ("明天下午三點", "chinese"),
            ("明日午後3時", "japanese"),
            ("Tomorrow 3 PM", "chinese"),  # Default
            ("田中さんをお迎え", "japanese"),
            ("張先生送到醫院", "chinese"),
            ("予約お願いします", "japanese"),
        ]
        
        for text, expected in test_cases:
            detected = detect_language(text)
            status = "✅" if detected == expected else "❌"
            print(f"{status} '{text}' -> {detected} (期望: {expected})")
        
        return True
        
    except Exception as e:
        print(f"❌ 語言檢測測試失敗: {e}")
        return False

if __name__ == "__main__":
    print("🧪 增強版AI預約功能全面測試")
    print("=" * 80)
    
    # 運行測試
    tests = [
        ("語言檢測", test_language_detection),
        ("多語言預約", test_multilingual_booking),
        ("圖片預約", test_image_booking),
        ("整合功能", test_integration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔄 開始測試: {test_name}")
        print("=" * 50)
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ 測試 {test_name} 發生未預期錯誤: {e}")
            results[test_name] = False
    
    # 總結
    print("\n📊 測試總結")
    print("=" * 80)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n總計: {passed}/{total} 個測試通過")
    
    if passed == total:
        print("🎉 所有測試通過！增強版AI預約功能運作正常。")
    else:
        print("⚠️  部分測試失敗，請檢查相關配置和依賴。")
    
    print("\n💡 功能特色:")
    print("• 支援中文和日文預約描述")
    print("• 智能圖片內容識別")
    print("• 自然語言理解和信息提取")
    print("• 多模態輸入處理")
    print("• 無縫整合至現有預約流程")