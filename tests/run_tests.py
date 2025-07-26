#!/usr/bin/env python3
"""
測試運行器
提供不同的測試運行選項和報告生成
"""
import os
import sys
import unittest
import pytest
import subprocess
from datetime import datetime


class TestRunner:
    """測試運行器類"""
    
    def __init__(self):
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.test_dir)
        
        # 添加項目根目錄到Python路徑
        if self.project_root not in sys.path:
            sys.path.insert(0, self.project_root)
    
    def run_unittest_suite(self, test_pattern="test_*.py", verbosity=2):
        """運行unittest測試套件"""
        print(f"🧪 運行unittest測試套件 (模式: {test_pattern})")
        print("=" * 60)
        
        # 發現測試
        loader = unittest.TestLoader()
        suite = loader.discover(
            start_dir=self.test_dir,
            pattern=test_pattern,
            top_level_dir=self.project_root
        )
        
        # 運行測試
        runner = unittest.TextTestRunner(
            verbosity=verbosity,
            stream=sys.stdout,
            buffer=True
        )
        
        result = runner.run(suite)
        
        # 輸出結果摘要
        self._print_unittest_summary(result)
        
        return result.wasSuccessful()
    
    def run_pytest_suite(self, test_files=None, markers=None, verbose=True):
        """運行pytest測試套件"""
        print("🧪 運行pytest測試套件")
        print("=" * 60)
        
        # 構建pytest命令
        cmd = ["python", "-m", "pytest"]
        
        if verbose:
            cmd.append("-v")
        
        # 添加測試文件
        if test_files:
            cmd.extend(test_files)
        else:
            cmd.append(self.test_dir)
        
        # 添加標記過濾
        if markers:
            cmd.extend(["-m", markers])
        
        # 添加覆蓋率報告
        cmd.extend([
            "--cov=modules",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov"
        ])
        
        # 運行pytest
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            return result.returncode == 0
        except FileNotFoundError:
            print("❌ pytest未安裝，請運行: pip install pytest pytest-cov")
            return False
    
    def run_specific_tests(self, test_categories):
        """運行特定類別的測試"""
        category_files = {
            'models': 'test_models.py',
            'services': 'test_services.py',
            'handlers': 'test_handlers.py',
            'ai': 'test_ai_system.py',
            'utils': 'test_utils.py',
            'integration': 'test_integration.py'
        }
        
        success = True
        
        for category in test_categories:
            if category in category_files:
                print(f"\n🎯 運行 {category.upper()} 測試")
                print("-" * 40)
                
                test_file = os.path.join(self.test_dir, category_files[category])
                if os.path.exists(test_file):
                    # 使用unittest運行單個文件
                    result = self._run_single_test_file(test_file)
                    success = success and result
                else:
                    print(f"⚠️  測試文件不存在: {category_files[category]}")
            else:
                print(f"❌ 未知的測試類別: {category}")
                success = False
        
        return success
    
    def run_quick_tests(self):
        """運行快速測試（排除慢速和外部依賴測試）"""
        print("⚡ 運行快速測試套件")
        print("=" * 60)
        
        # 使用pytest排除慢速測試
        cmd = [
            "python", "-m", "pytest",
            "-v",
            "-m", "not slow and not external",
            self.test_dir
        ]
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            return result.returncode == 0
        except FileNotFoundError:
            # 回退到unittest
            return self.run_unittest_suite(verbosity=1)
    
    def run_ai_tests(self):
        """運行AI系統相關測試"""
        print("🤖 運行AI系統測試")
        print("=" * 60)
        
        ai_test_file = os.path.join(self.test_dir, "test_ai_system.py")
        return self._run_single_test_file(ai_test_file)
    
    def run_integration_tests(self):
        """運行整合測試"""
        print("🔗 運行整合測試")
        print("=" * 60)
        
        integration_test_file = os.path.join(self.test_dir, "test_integration.py")
        return self._run_single_test_file(integration_test_file)
    
    def run_coverage_analysis(self):
        """運行覆蓋率分析"""
        print("📊 運行測試覆蓋率分析")
        print("=" * 60)
        
        cmd = [
            "python", "-m", "pytest",
            "--cov=modules",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-report=xml:coverage.xml",
            self.test_dir
        ]
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            
            if result.returncode == 0:
                print("\n✅ 覆蓋率報告已生成:")
                print("   - HTML報告: htmlcov/index.html")
                print("   - XML報告: coverage.xml")
            
            return result.returncode == 0
        except FileNotFoundError:
            print("❌ pytest-cov未安裝，請運行: pip install pytest-cov")
            return False
    
    def _run_single_test_file(self, test_file):
        """運行單個測試文件"""
        if not os.path.exists(test_file):
            print(f"❌ 測試文件不存在: {test_file}")
            return False
        
        # 導入並運行測試
        try:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(
                os.path.splitext(os.path.basename(test_file))[0]
            )
            
            runner = unittest.TextTestRunner(verbosity=2, buffer=True)
            result = runner.run(suite)
            
            return result.wasSuccessful()
        except Exception as e:
            print(f"❌ 運行測試時發生錯誤: {e}")
            return False
    
    def _print_unittest_summary(self, result):
        """打印unittest結果摘要"""
        print("\n" + "=" * 60)
        print("📋 測試結果摘要")
        print("=" * 60)
        
        print(f"✅ 運行測試: {result.testsRun}")
        print(f"❌ 失敗: {len(result.failures)}")
        print(f"💥 錯誤: {len(result.errors)}")
        print(f"⏭️  跳過: {len(result.skipped)}")
        
        if result.failures:
            print(f"\n❌ 失敗的測試:")
            for test, traceback in result.failures:
                print(f"   - {test}")
        
        if result.errors:
            print(f"\n💥 錯誤的測試:")
            for test, traceback in result.errors:
                print(f"   - {test}")
        
        if result.wasSuccessful():
            print(f"\n🎉 所有測試通過！")
        else:
            print(f"\n⚠️  有測試失敗，請檢查上述問題")
    
    def generate_test_report(self):
        """生成測試報告"""
        print("📄 生成測試報告")
        print("=" * 60)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.project_root, f"test_report_{timestamp}.html")
        
        cmd = [
            "python", "-m", "pytest",
            "--html=" + report_file,
            "--self-contained-html",
            self.test_dir
        ]
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            
            if result.returncode == 0:
                print(f"✅ 測試報告已生成: {report_file}")
            
            return result.returncode == 0
        except FileNotFoundError:
            print("❌ pytest-html未安裝，請運行: pip install pytest-html")
            return False


def main():
    """主函數"""
    runner = TestRunner()
    
    if len(sys.argv) < 2:
        # 默認運行所有測試
        print("🚀 運行完整測試套件")
        success = runner.run_unittest_suite()
    else:
        command = sys.argv[1].lower()
        
        if command == "quick":
            success = runner.run_quick_tests()
        elif command == "ai":
            success = runner.run_ai_tests()
        elif command == "integration":
            success = runner.run_integration_tests()
        elif command == "coverage":
            success = runner.run_coverage_analysis()
        elif command == "report":
            success = runner.generate_test_report()
        elif command == "pytest":
            success = runner.run_pytest_suite()
        elif command in ["models", "services", "handlers", "utils"]:
            success = runner.run_specific_tests([command])
        elif command == "help":
            print_help()
            return 0
        else:
            print(f"❌ 未知命令: {command}")
            print_help()
            return 1
    
    return 0 if success else 1


def print_help():
    """打印幫助信息"""
    print("""
🧪 測試運行器使用說明

用法: python run_tests.py [命令]

可用命令:
  (無參數)    運行完整測試套件
  quick      運行快速測試（排除慢速測試）
  ai         運行AI系統測試
  integration 運行整合測試
  models     運行模型測試
  services   運行服務測試
  handlers   運行處理器測試
  utils      運行工具測試
  coverage   運行覆蓋率分析
  report     生成HTML測試報告
  pytest     使用pytest運行測試
  help       顯示此幫助信息

示例:
  python run_tests.py                # 運行所有測試
  python run_tests.py quick          # 快速測試
  python run_tests.py ai             # AI系統測試
  python run_tests.py coverage       # 覆蓋率分析

注意：
- 需要安裝pytest和相關插件才能使用所有功能
- 建議運行: pip install pytest pytest-cov pytest-html
""")


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)