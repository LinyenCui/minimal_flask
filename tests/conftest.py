#!/usr/bin/env python3
"""
pytest 配置文件
定義測試夾具、配置和共享測試工具
"""
import pytest
import os
import tempfile
from datetime import datetime, date, timedelta

# 確保測試環境變數
os.environ['TESTING'] = 'True'
os.environ['FLASK_ENV'] = 'testing'


@pytest.fixture(scope="session")
def app():
    """創建測試應用實例"""
    from modules import create_app
    from modules.models.base import db
    
    # 創建臨時資料庫
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key'
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
    
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope="function")
def client(app):
    """創建測試客戶端"""
    return app.test_client()


@pytest.fixture(scope="function")
def runner(app):
    """創建CLI運行器"""
    return app.test_cli_runner()


@pytest.fixture(scope="function")
def db_session(app):
    """創建資料庫會話"""
    from modules.models.base import db
    
    with app.app_context():
        # 清理測試數據
        db.session.rollback()
        
        # 清空所有表
        meta = db.metadata
        for table in reversed(meta.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        
        yield db.session
        
        # 測試後清理
        db.session.rollback()


@pytest.fixture(scope="function")
def sample_drivers(db_session):
    """創建示例司機數據"""
    from modules.models.driver import Driver
    
    drivers = [
        Driver(id=533, name="王司機", plate_number="ABC-1234"),
        Driver(id=534, name="李司機", plate_number="DEF-5678"),
        Driver(id=535, name="張司機", plate_number="GHI-9012")
    ]
    
    for driver in drivers:
        db_session.add(driver)
    db_session.commit()
    
    return drivers


@pytest.fixture(scope="function")
def sample_customers(db_session):
    """創建示例客戶數據"""
    from modules.models.customer import Customer
    
    customers = [
        Customer(id=1, name="診所", address="台南市中西區", category="醫療"),
        Customer(id=2, name="東洋", address="高雄市", category="企業"),
        Customer(id=3, name="醫院", address="台南市東區", category="醫療")
    ]
    
    for customer in customers:
        db_session.add(customer)
    db_session.commit()
    
    return customers


@pytest.fixture(scope="function")
def sample_fixed_schedules(db_session):
    """創建示例固定班次"""
    from modules.models.trip import FixedSchedule
    
    schedules = [
        FixedSchedule(
            id=1,
            route_number="R001",
            departure_time="08:00",
            day_of_week=1,  # 星期一
            start_point="高鐵站",
            end_point="診所",
            base_fare=200,
            total_fare=220,
            category="醫療"
        ),
        FixedSchedule(
            id=2,
            route_number="R002",
            departure_time="09:30", 
            day_of_week=2,  # 星期二
            start_point="公司",
            end_point="東洋",
            base_fare=150,
            total_fare=180,
            category="企業"
        ),
        FixedSchedule(
            id=3,
            route_number="R003",
            departure_time="14:00",
            day_of_week=5,  # 星期五
            start_point="醫院",
            end_point="家",
            base_fare=100,
            total_fare=120,
            category="醫療"
        )
    ]
    
    for schedule in schedules:
        db_session.add(schedule)
    db_session.commit()
    
    return schedules


@pytest.fixture(scope="function")
def sample_trips(db_session, sample_drivers, sample_fixed_schedules):
    """創建示例班次數據"""
    from modules.models.trip import Trip
    
    today = date.today()
    
    trips = [
        Trip(
            id=100,
            date=today,
            time="10:00",
            start_point="高鐵站",
            end_point="診所",
            actual_fare=220,
            category="醫療",
            status="待派",
            fixed_trip_id=1
        ),
        Trip(
            id=101,
            date=today,
            time="14:30",
            start_point="公司",
            end_point="東洋",
            actual_fare=180,
            category="企業",
            status="準備",
            driver_id=533,
            fixed_trip_id=2
        ),
        Trip(
            id=102,
            date=today,
            time="16:00",
            start_point="醫院",
            end_point="家",
            actual_fare=120,
            category="臨時",
            status="完成",
            driver_id=534
        ),
        Trip(
            id=103,
            date=today - timedelta(days=1),
            time="09:00",
            start_point="昨日起點",
            end_point="昨日終點",
            actual_fare=200,
            category="醫療",
            status="完成",
            driver_id=535
        )
    ]
    
    for trip in trips:
        db_session.add(trip)
    db_session.commit()
    
    return trips


@pytest.fixture(scope="function")
def sample_completed_trips(db_session, sample_drivers):
    """創建示例已完成班次"""
    from modules.models.trip import CompletedTrip
    
    completed_trips = [
        CompletedTrip(
            original_trip_id=200,
            date=date.today() - timedelta(days=7),
            time="08:00",
            start_point="上週起點1",
            end_point="上週終點1",
            actual_fare=250,
            driver_id=533,
            category="醫療",
            completed_at=datetime.now() - timedelta(days=7)
        ),
        CompletedTrip(
            original_trip_id=201,
            date=date.today() - timedelta(days=6),
            time="10:30",
            start_point="上週起點2",
            end_point="上週終點2",
            actual_fare=180,
            driver_id=534,
            category="企業",
            completed_at=datetime.now() - timedelta(days=6)
        ),
        CompletedTrip(
            original_trip_id=202,
            date=date.today() - timedelta(days=5),
            time="15:00",
            start_point="上週起點3",
            end_point="上週終點3",
            actual_fare=300,
            driver_id=535,
            category="醫療",
            completed_at=datetime.now() - timedelta(days=5)
        )
    ]
    
    for trip in completed_trips:
        db_session.add(trip)
    db_session.commit()
    
    return completed_trips


@pytest.fixture(scope="function")
def mock_line_event():
    """創建模擬LINE事件"""
    from unittest.mock import Mock
    
    event = Mock()
    event.message.text = "測試消息"
    event.source.user_id = "test_user_id"
    event.reply_token = "test_reply_token"
    event.type = "message"
    event.message.type = "text"
    
    return event


@pytest.fixture(scope="function")
def mock_gemini_response():
    """創建模擬Gemini響應"""
    from unittest.mock import Mock
    
    response = Mock()
    response.text = "這是模擬的Gemini回應"
    
    return response


@pytest.fixture(scope="function")
def mock_gemini_client(mock_gemini_response):
    """創建模擬Gemini客戶端"""
    from unittest.mock import Mock
    
    client = Mock()
    client.generate_content.return_value = mock_gemini_response
    
    return client


# 測試標記
def pytest_configure(config):
    """配置pytest標記"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "ai: marks tests that require AI services"
    )
    config.addinivalue_line(
        "markers", "database: marks tests that require database"
    )
    config.addinivalue_line(
        "markers", "external: marks tests that require external services"
    )


# 測試數據生成工具
class TestDataFactory:
    """測試數據工廠"""
    
    @staticmethod
    def create_trip(**kwargs):
        """創建測試班次"""
        from modules.models.trip import Trip
        
        defaults = {
            'date': date.today(),
            'time': '10:00',
            'start_point': '測試起點',
            'end_point': '測試終點',
            'actual_fare': 150,
            'category': '測試',
            'status': '待派'
        }
        defaults.update(kwargs)
        
        return Trip(**defaults)
    
    @staticmethod
    def create_driver(**kwargs):
        """創建測試司機"""
        from modules.models.driver import Driver
        
        defaults = {
            'name': '測試司機',
            'plate_number': 'TEST-123'
        }
        defaults.update(kwargs)
        
        return Driver(**defaults)
    
    @staticmethod
    def create_customer(**kwargs):
        """創建測試客戶"""
        from modules.models.customer import Customer
        
        defaults = {
            'name': '測試客戶',
            'address': '測試地址',
            'category': '測試'
        }
        defaults.update(kwargs)
        
        return Customer(**defaults)


@pytest.fixture(scope="function")
def data_factory():
    """提供測試數據工廠"""
    return TestDataFactory


# 測試斷言助手
class TestAssertions:
    """測試斷言助手"""
    
    @staticmethod
    def assert_trip_equals(trip1, trip2, ignore_fields=None):
        """斷言兩个班次相等"""
        ignore_fields = ignore_fields or ['id', 'created_at', 'updated_at']
        
        for attr in ['date', 'time', 'start_point', 'end_point', 'actual_fare', 'status']:
            if attr not in ignore_fields:
                assert getattr(trip1, attr) == getattr(trip2, attr), f"Field {attr} differs"
    
    @staticmethod
    def assert_valid_flex_message(flex_content):
        """斷言有效的Flex消息格式"""
        assert 'type' in flex_content
        assert flex_content['type'] in ['bubble', 'carousel']
        
        if flex_content['type'] == 'bubble':
            assert 'body' in flex_content
            assert flex_content['body']['type'] == 'box'


@pytest.fixture(scope="function")
def assertions():
    """提供測試斷言助手"""
    return TestAssertions


# 環境清理
@pytest.fixture(autouse=True)
def cleanup_test_environment():
    """自動清理測試環境"""
    # 測試前設置
    yield
    
    # 測試後清理
    # 這裡可以添加清理邏輯，如清理臨時文件、重置全局狀態等


# Mock工具
@pytest.fixture
def mock_line_bot_api():
    """Mock LINE Bot API"""
    from unittest.mock import Mock, patch
    
    with patch('modules.utils.line_bot.line_bot_api') as mock_api:
        mock_api.push_message = Mock()
        mock_api.reply_message = Mock()
        mock_api.broadcast = Mock()
        yield mock_api


@pytest.fixture
def mock_gemini_service():
    """Mock Gemini AI服務"""
    from unittest.mock import Mock, patch
    
    with patch('modules.ai_agent.gemini_client.get_gemini_client') as mock_get_client:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "模擬AI回應"
        mock_client.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_google_drive():
    """Mock Google Drive服務"""
    from unittest.mock import Mock, patch
    
    with patch('modules.services.drive_service.upload_to_drive') as mock_upload:
        mock_upload.return_value = "https://drive.google.com/file/test-id"
        yield mock_upload


# 性能測試工具
@pytest.fixture
def performance_timer():
    """性能計時器"""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()