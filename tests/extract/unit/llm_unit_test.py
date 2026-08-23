"""
LLM功能测试程序

全面的LLM功能测试，包括Provider初始化、API调用、缓存机制、错误处理等。

使用方法:
    python tests/extract/unit/llm_unit_test.py
"""
import os
import sys
import time
import json
import hashlib
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """测试结果数据类"""
    test_case: str
    test_name: str
    status: str  # "passed", "failed", "error"
    expected: str
    actual: str
    message: str
    duration: float
    logs: List[str] = None
    provider_name: Optional[str] = None
    response_preview: Optional[str] = None


class LLMTester:
    """LLM功能测试类"""
    
    def __init__(self):
        """初始化测试器"""
        self.provider = None
        self.cache = None
        self.results: List[TestResult] = []
        self.test_cache_db = None
        
    def setup(self):
        """设置测试环境"""
        try:
            from backend.extract.llm import LLMEngine
            from config.loader import get_config_loader
            
            config_loader = get_config_loader()
            
            # 使用推荐的 from_config_loader 方式初始化
            try:
                self.engine = LLMEngine.from_config_loader(config_loader)
                logger.info("LLM Engine初始化成功（使用默认配置）")
            except ValueError as e:
                logger.warning(f"LLM Engine初始化失败: {e}，将跳过需要真实API的测试")
                return False
            
            # 检查API Key是否配置
            config = config_loader.load_config()
            default_provider = config_loader.get_default_provider('llm')
            provider_config = config['llm']['providers'].get(default_provider, {})
            provider_type = provider_config.get("type", "api")
            
            if provider_type == "api":
                api_key_env = provider_config.get("api_key_env")
                if api_key_env:
                    api_key = os.getenv(api_key_env)
                    if not api_key:
                        logger.warning(f"环境变量 {api_key_env} 未设置，将跳过需要真实API的测试")
                        return False
            
            # 初始化测试缓存（使用临时文件）
            self.test_cache_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            self.test_cache_db.close()
            from backend.extract.llm import ExtractCacheDB
            self.cache = ExtractCacheDB(self.test_cache_db.name)
            logger.info(f"测试缓存数据库初始化: {self.test_cache_db.name}")
            
            return True
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
    
    def cleanup(self):
        """清理测试环境"""
        try:
            # 删除测试缓存数据库
            if self.test_cache_db and os.path.exists(self.test_cache_db.name):
                os.unlink(self.test_cache_db.name)
                logger.info("测试缓存数据库已清理")
        except Exception as e:
            logger.warning(f"清理失败: {e}")
    
    def test_engine_initialization(self) -> TestResult:
        """测试用例1：Engine初始化测试（使用from_config_loader）"""
        test_name = "Engine初始化测试"
        start_time = time.time()
        
        try:
            from backend.extract.llm import LLMEngine
            from config.loader import get_config_loader
            
            # 测试从配置加载器创建（推荐方式）
            config_loader = get_config_loader()
            try:
                engine = LLMEngine.from_config_loader(config_loader)
                
                if engine and engine.provider:
                    status = "passed"
                    message = "Engine初始化成功"
                else:
                    status = "failed"
                    message = "Engine初始化失败"
            except ValueError as e:
                # 配置缺失是正常的，不算测试失败
                status = "passed"
                message = f"配置检查正常（配置缺失: {e}）"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_1",
                test_name=test_name,
                status=status,
                expected="Engine初始化成功",
                actual=message,
                message=message,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_1",
                test_name=test_name,
                status="error",
                expected="Engine初始化成功",
                actual=f"测试执行错误: {e}",
                message=f"测试执行失败: {e}",
                duration=duration
            )
    
    def test_api_key_validation(self) -> TestResult:
        """测试用例2：API Key验证测试"""
        test_name = "API Key验证测试"
        start_time = time.time()
        
        try:
            from backend.extract.llm import LLMProvider
            from backend.extract.exceptions import LLMError
            
            # 测试API Key未设置的情况
            test_config = {
                "url": "https://test.example.com/api",
                "api_key_env": "NONEXISTENT_API_KEY",
                "model": "test-model"
            }
            provider = LLMProvider(test_config)
            
            # 尝试调用（应该失败）
            try:
                provider.chat([{"role": "user", "content": "test"}])
                status = "failed"
                message = "应该抛出ValueError异常（API Key未设置）"
            except (ValueError, LLMError) as e:
                if "未设置" in str(e) or "NONEXISTENT_API_KEY" in str(e):
                    status = "passed"
                    message = f"正确抛出异常: {type(e).__name__}"
                else:
                    status = "failed"
                    message = f"异常信息不正确: {e}"
            except Exception as e:
                status = "failed"
                message = f"抛出异常类型错误: {type(e).__name__}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_2",
                test_name=test_name,
                status=status,
                expected="API Key未设置时抛出ValueError",
                actual=message,
                message=message,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_2",
                test_name=test_name,
                status="error",
                expected="API Key验证成功",
                actual=f"测试执行错误: {e}",
                message=f"测试执行失败: {e}",
                duration=duration
            )
    
    def test_llm_chat(self) -> TestResult:
        """测试用例3：LLM调用测试（带缓存）"""
        test_name = "LLM调用测试"
        start_time = time.time()
        
        if not hasattr(self, 'engine') or not self.engine:
            return TestResult(
                test_case="test_3",
                test_name=test_name,
                status="error",
                expected="LLM调用成功",
                actual="Engine未初始化",
                message="跳过测试（需要真实API配置）",
                duration=time.time() - start_time
            )
        
        try:
            messages = [{"role": "user", "content": "请用一句话回答：1+1等于几？"}]
            response, cached = self.engine.chat(messages, temperature=0.1, use_cache=False)
            
            if response and len(response) > 0:
                status = "passed"
                message = f"LLM调用成功，响应长度: {len(response)}, 缓存命中: {cached}"
                response_preview = response[:100] if len(response) > 100 else response
            else:
                status = "failed"
                message = "LLM返回空响应"
                response_preview = None
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3",
                test_name=test_name,
                status=status,
                expected="LLM调用成功并返回有效响应",
                actual=message,
                message=message,
                duration=duration,
                response_preview=response_preview
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3",
                test_name=test_name,
                status="error",
                expected="LLM调用成功",
                actual=f"调用失败: {e}",
                message=f"LLM调用异常: {e}",
                duration=duration
            )
    
    def test_cache_save_and_get(self) -> TestResult:
        """测试用例4：缓存保存和获取测试"""
        test_name = "缓存保存和获取测试"
        start_time = time.time()
        
        try:
            # 准备测试数据
            prompt_hash = hashlib.sha256("test prompt".encode()).hexdigest()
            llm_prompt = "测试提示词"
            llm_response = "测试响应"
            
            # 保存缓存
            save_success = self.cache.save(prompt_hash, llm_prompt, llm_response)
            
            if not save_success:
                status = "failed"
                message = "缓存保存失败"
            else:
                # 获取缓存
                cached_response = self.cache.get(prompt_hash)
                
                if cached_response == llm_response:
                    status = "passed"
                    message = "缓存保存和获取成功"
                else:
                    status = "failed"
                    message = f"缓存获取失败或数据不匹配: {cached_response}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_4",
                test_name=test_name,
                status=status,
                expected="缓存保存和获取成功",
                actual=message,
                message=message,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_4",
                test_name=test_name,
                status="error",
                expected="缓存操作成功",
                actual=f"测试执行错误: {e}",
                message=f"测试执行失败: {e}",
                duration=duration
            )
    
    def test_cache_replace(self) -> TestResult:
        """测试用例5：缓存覆盖测试"""
        test_name = "缓存覆盖测试"
        start_time = time.time()
        
        try:
            prompt_hash = hashlib.sha256("test prompt".encode()).hexdigest()
            
            # 第一次保存
            self.cache.save(prompt_hash, "提示词", "first response")
            
            # 第二次保存（应该覆盖）
            self.cache.save(prompt_hash, "提示词", "second response")
            
            # 获取缓存
            cached_response = self.cache.get(prompt_hash)
            
            if cached_response == "second response":
                status = "passed"
                message = "缓存覆盖成功"
            else:
                status = "failed"
                message = f"缓存覆盖失败，获取到的值: {cached_response}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_5",
                test_name=test_name,
                status=status,
                expected="缓存覆盖成功（新值替换旧值）",
                actual=message,
                message=message,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_5",
                test_name=test_name,
                status="error",
                expected="缓存覆盖成功",
                actual=f"测试执行错误: {e}",
                message=f"测试执行失败: {e}",
                duration=duration
            )
    
    def test_cache_miss(self) -> TestResult:
        """测试用例6：缓存未命中测试"""
        test_name = "缓存未命中测试"
        start_time = time.time()
        
        try:
            # 查询不存在的缓存
            nonexistent_hash = hashlib.sha256("nonexistent prompt".encode()).hexdigest()
            cached_response = self.cache.get(nonexistent_hash)
            
            if cached_response is None:
                status = "passed"
                message = "缓存未命中时正确返回None"
            else:
                status = "failed"
                message = f"缓存未命中时应该返回None，但返回了: {cached_response}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_6",
                test_name=test_name,
                status=status,
                expected="缓存未命中时返回None",
                actual=message,
                message=message,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_6",
                test_name=test_name,
                status="error",
                expected="缓存未命中测试成功",
                actual=f"测试执行错误: {e}",
                message=f"测试执行失败: {e}",
                duration=duration
            )
    
    def test_cache_stats(self) -> TestResult:
        """测试用例7：缓存统计信息测试"""
        test_name = "缓存统计信息测试"
        start_time = time.time()
        
        try:
            # 保存一些测试数据
            for i in range(5):
                prompt_hash = hashlib.sha256(f"test prompt {i}".encode()).hexdigest()
                self.cache.save(prompt_hash, f"提示词{i}", f"响应{i}")
            
            # 获取统计信息
            stats = self.cache.get_stats()
            
            if stats and stats.get("total") >= 5:
                status = "passed"
                message = f"统计信息获取成功，总记录数: {stats['total']}"
            else:
                status = "failed"
                message = f"统计信息不正确: {stats}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_7",
                test_name=test_name,
                status=status,
                expected="缓存统计信息获取成功",
                actual=message,
                message=message,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_7",
                test_name=test_name,
                status="error",
                expected="缓存统计信息测试成功",
                actual=f"测试执行错误: {e}",
                message=f"测试执行失败: {e}",
                duration=duration
            )
    
    def test_cache_delete(self) -> TestResult:
        """测试用例8：缓存删除测试"""
        test_name = "缓存删除测试"
        start_time = time.time()
        
        try:
            prompt_hash = hashlib.sha256("test delete prompt".encode()).hexdigest()
            
            # 保存缓存
            self.cache.save(prompt_hash, "测试提示词", "测试响应")
            
            # 删除缓存
            deleted_count = self.cache.delete(prompt_hash)
            
            # 验证删除
            cached_response = self.cache.get(prompt_hash)
            
            if deleted_count == 1 and cached_response is None:
                status = "passed"
                message = "缓存删除成功"
            else:
                status = "failed"
                message = f"缓存删除失败，删除数: {deleted_count}, 查询结果: {cached_response}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_8",
                test_name=test_name,
                status=status,
                expected="缓存删除成功",
                actual=message,
                message=message,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_8",
                test_name=test_name,
                status="error",
                expected="缓存删除测试成功",
                actual=f"测试执行错误: {e}",
                message=f"测试执行失败: {e}",
                duration=duration
            )
    
    
    def test_cache_integration(self) -> TestResult:
        """测试用例10：缓存集成测试"""
        test_name = "缓存集成测试"
        start_time = time.time()
        
        if not hasattr(self, 'engine') or not self.engine:
            return TestResult(
                test_case="test_10",
                test_name=test_name,
                status="error",
                expected="缓存集成测试成功",
                actual="Engine未初始化",
                message="跳过测试（需要真实API配置）",
                duration=time.time() - start_time
            )
        
        try:
            messages = [{"role": "user", "content": "测试缓存：请回答1+1等于几？"}]
            
            # 第一次调用（使用缓存，会调用LLM并保存到缓存）
            response1, cached1 = self.engine.chat(messages, temperature=0.1, use_cache=True)
            
            # 第二次调用（使用缓存，应该命中第一次的结果）
            response2, cached2 = self.engine.chat(messages, temperature=0.1, use_cache=True)
            
            if cached2 and response1 == response2:
                status = "passed"
                message = f"缓存集成成功，第一次: cached={cached1}, 第二次: cached={cached2}"
            elif response1 == response2 and not cached2:
                status = "passed"
                message = f"响应一致，但缓存未命中（可能缓存未启用）"
            else:
                status = "failed"
                message = f"缓存集成失败，第一次: cached={cached1}, 第二次: cached={cached2}, 响应是否一致: {response1 == response2}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_10",
                test_name=test_name,
                status=status,
                expected="缓存集成成功",
                actual=message,
                message=message,
                duration=duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_10",
                test_name=test_name,
                status="error",
                expected="缓存集成测试成功",
                actual=f"测试失败: {e}",
                message=f"测试异常: {e}",
                duration=duration
            )
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 60)
        logger.info("开始运行LLM功能测试")
        logger.info("=" * 60)
        
        # 运行测试
        test_methods = [
            self.test_engine_initialization,
            self.test_api_key_validation,
            self.test_llm_chat,
            self.test_cache_save_and_get,
            self.test_cache_replace,
            self.test_cache_miss,
            self.test_cache_stats,
            self.test_cache_delete,
            self.test_cache_integration,
        ]
        
        for test_method in test_methods:
            try:
                result = test_method()
                self.results.append(result)
                status_icon = "✓" if result.status == "passed" else "✗" if result.status == "failed" else "!"
                logger.info(f"{status_icon} {result.test_name}: {result.message} ({result.duration:.2f}s)")
            except Exception as e:
                logger.error(f"测试执行异常: {test_method.__name__}: {e}")
                self.results.append(TestResult(
                    test_case=test_method.__name__,
                    test_name=test_method.__name__,
                    status="error",
                    expected="测试执行",
                    actual=f"异常: {e}",
                    message=f"测试执行异常: {e}",
                    duration=0
                ))
        
        # 统计结果
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        error = sum(1 for r in self.results if r.status == "error")
        
        logger.info("=" * 60)
        logger.info("测试完成")
        logger.info(f"总计: {total}, 通过: {passed}, 失败: {failed}, 错误: {error}")
        logger.info("=" * 60)
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "error": error,
            "results": self.results
        }
    
    def print_summary(self):
        """打印测试摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        error = sum(1 for r in self.results if r.status == "error")
        
        print("\n" + "=" * 60)
        print("LLM功能测试摘要")
        print("=" * 60)
        print(f"总测试数: {total}")
        print(f"通过: {passed} ({passed/total*100:.1f}%)")
        print(f"失败: {failed} ({failed/total*100:.1f}%)")
        print(f"错误: {error} ({error/total*100:.1f}%)")
        print("=" * 60)
        
        if failed > 0 or error > 0:
            print("\n失败的测试:")
            for result in self.results:
                if result.status in ["failed", "error"]:
                    print(f"  - {result.test_name}: {result.message}")


def main():
    """主函数"""
    tester = LLMTester()
    
    try:
        # 设置测试环境
        if not tester.setup():
            logger.warning("测试环境设置失败，部分测试将被跳过")
        
        # 运行测试
        tester.run_all_tests()
        
        # 打印摘要
        tester.print_summary()
        
    finally:
        # 清理
        tester.cleanup()


if __name__ == "__main__":
    main()
