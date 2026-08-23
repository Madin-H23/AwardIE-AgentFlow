"""
OCR功能测试程序

全面的OCR功能测试，包括错误处理、PDF处理、缓存机制、图片预处理和识别效果等。

使用方法:
    python tests/ocr/test_ocr.py
"""
import os
import sys
import time
import base64
import hashlib
import logging
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 测试文件列表
test_files_list = [
    {
        "name": "奖状图片",
        "path": "images\测试图片\奖状\国赛_项目实战赛_项目实战赛-智能体开发大学组_二等奖_陈品天_1663002033_2395708.jpg",
        "type": "award",
        "description": "普通的奖状图片，包含中文文字"
    }
]


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
    image_path: Optional[str] = None
    precise_result: Optional[str] = None
    fast_result: Optional[str] = None


def clear_image_cache(engine, file_path: str) -> bool:
    """
    清理指定图片的OCR缓存（测试辅助函数）
    
    Args:
        engine: OCREngine实例
        file_path: 图片文件路径
        
    Returns:
        是否清理成功
    """
    try:
        # 计算文件hash（基于文件内容，不包含Provider信息）
        import hashlib
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        file_hash = sha256.hexdigest()
        
        # 删除缓存（通过hash）
        count = engine.cache_db.delete_ocr_cache(file_hash)
        return count > 0
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        return False


def get_image_size(file_path: str) -> Tuple[int, int]:
    """获取图片尺寸"""
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            return img.size
    except:
        return (0, 0)


def image_to_base64(image_path: str) -> str:
    """将图片转换为 base64 编码"""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except:
        return ""


def calculate_similarity(text1: str, text2: str) -> float:
    """计算两个文本的相似度 (0-1)"""
    from difflib import SequenceMatcher
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1, text2).ratio()


class OCRTester:
    """OCR功能测试类"""
    
    def __init__(self):
        """初始化测试器"""
        self.engine = None
        self.results: List[TestResult] = []
        self.test_files = []
        
        # 加载测试文件
        for file_info in test_files_list:
            file_path = project_root / file_info["path"]
            if file_path.exists():
                self.test_files.append({
                    **file_info,
                    "full_path": str(file_path)
                })
            else:
                logger.warning(f"测试文件不存在: {file_path}")
    
    def setup(self):
        """设置测试环境"""
        try:
            from backend.ocr import OCREngine
            from config.loader import get_config_loader
            
            config_loader = get_config_loader()
            self.engine = OCREngine.from_config_loader(config_loader)
            logger.info("OCR引擎初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
    
    def test_file_not_found(self) -> TestResult:
        """测试用例1：文件路径错误测试"""
        test_name = "文件路径错误测试"
        start_time = time.time()
        
        try:
            # 测试不存在的文件
            try:
                self.engine.get_text("nonexistent_file.jpg", use_cache=False)
                status = "failed"
                message = "应该抛出OCRFileNotFoundError异常"
            except Exception as e:
                if "OCRFileNotFoundError" in str(type(e)) or "未找到文件" in str(e):
                    status = "passed"
                    message = f"正确抛出异常: {type(e).__name__}"
                else:
                    status = "failed"
                    message = f"抛出异常类型错误: {type(e).__name__}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_1",
                test_name=test_name,
                status=status,
                expected="抛出OCRFileNotFoundError异常",
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
                expected="抛出OCRFileNotFoundError异常",
                actual=f"测试执行错误: {e}",
                message=f"测试执行失败: {e}",
                duration=duration
            )
    
    def test_pdf_processing(self) -> TestResult:
        """测试用例2：PDF文件识别测试"""
        test_name = "PDF文件识别测试"
        start_time = time.time()
        
        pdf_file = None
        for file_info in self.test_files:
            if file_info["type"] == "pdf":
                pdf_file = file_info
                break
        
        if not pdf_file:
            return TestResult(
                test_case="test_2",
                test_name=test_name,
                status="error",
                expected="PDF文件处理成功",
                actual="未找到PDF测试文件",
                message="测试文件缺失",
                duration=time.time() - start_time
            )
        
        try:
            pdf_path = pdf_file["full_path"]
            pdf_dir = Path(pdf_path).parent
            pdf_name = Path(pdf_path).stem
            expected_image_path = pdf_dir / f"{pdf_name}.png"
            
            # 清理可能存在的转换图片
            if expected_image_path.exists():
                expected_image_path.unlink()
            
            # 执行OCR
            text, cached = self.engine.get_text(pdf_path, use_cache=False, is_precise=True)
            
            # 验证转换后的图片是否存在
            image_exists = expected_image_path.exists()
            text_valid = bool(text and text.strip())
            
            if image_exists and text_valid:
                status = "passed"
                message = f"PDF转换成功，图片保存在: {expected_image_path.name}"
            elif not image_exists:
                status = "failed"
                message = f"PDF转换后的图片不存在: {expected_image_path}"
            else:
                status = "failed"
                message = "OCR识别失败或返回空文本"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_2",
                test_name=test_name,
                status=status,
                expected="PDF转换为图片并识别成功",
                actual=message,
                message=message,
                duration=duration,
                image_path=pdf_path
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_2",
                test_name=test_name,
                status="error",
                expected="PDF文件处理成功",
                actual=f"测试执行错误: {e}",
                message=f"测试执行失败: {e}",
                duration=duration
            )
    
    def test_cache_scenarios(self) -> List[TestResult]:
        """测试用例3：缓存命中测试（所有场景）"""
        results = []
        
        # 选择一个测试图片
        test_image = None
        for file_info in self.test_files:
            if file_info["type"] in ["award", "other"]:
                test_image = file_info
                break
        
        if not test_image:
            return [TestResult(
                test_case="test_3",
                test_name="缓存命中测试",
                status="error",
                expected="执行缓存测试",
                actual="未找到测试图片",
                message="测试文件缺失",
                duration=0
            )]
        
        image_path = test_image["full_path"]
        
        # 场景3.1：无缓存，高精度访问
        results.append(self._test_cache_scenario_3_1(image_path))
        
        # 场景3.2：无缓存，低精度访问
        results.append(self._test_cache_scenario_3_2(image_path))
        
        # 场景3.3：低精度缓存，要求高精度
        results.append(self._test_cache_scenario_3_3(image_path))
        
        # 场景3.4：高精度缓存，要求高精度
        results.append(self._test_cache_scenario_3_4(image_path))
        
        # 场景3.5：高精度缓存，要求低精度
        results.append(self._test_cache_scenario_3_5(image_path))
        
        # 场景3.6：低精度缓存，要求低精度
        results.append(self._test_cache_scenario_3_6(image_path))
        
        # 场景3.7：禁用缓存
        results.append(self._test_cache_scenario_3_7(image_path))
        
        return results
    
    def _test_cache_scenario_3_1(self, image_path: str) -> TestResult:
        """场景3.1：无缓存，高精度访问"""
        test_name = "缓存测试-场景3.1：无缓存，高精度访问"
        start_time = time.time()
        
        try:
            # 清理缓存
            clear_image_cache(self.engine, image_path)
            
            # 高精度访问
            text1, cached1 = self.engine.get_text(image_path, use_cache=True, is_precise=True)
            
            # 验证
            if not cached1 and text1:
                status = "passed"
                message = "正确：未命中缓存，执行OCR，创建高精度缓存"
            else:
                status = "failed"
                message = f"错误：cached={cached1}, text={'有内容' if text1 else '空'}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_1",
                test_name=test_name,
                status=status,
                expected="cached=False, 创建高精度缓存",
                actual=f"cached={cached1}, text_length={len(text1) if text1 else 0}",
                message=message,
                duration=duration,
                image_path=image_path
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_1",
                test_name=test_name,
                status="error",
                expected="执行成功",
                actual=f"错误: {e}",
                message=f"测试失败: {e}",
                duration=duration
            )
    
    def _test_cache_scenario_3_2(self, image_path: str) -> TestResult:
        """场景3.2：无缓存，低精度访问"""
        test_name = "缓存测试-场景3.2：无缓存，低精度访问"
        start_time = time.time()
        
        try:
            # 清理缓存
            clear_image_cache(self.engine, image_path)
            
            # 低精度访问
            text1, cached1 = self.engine.get_text(image_path, use_cache=True, is_precise=False)
            
            # 验证
            if not cached1 and text1:
                status = "passed"
                message = "正确：未命中缓存，执行OCR，创建低精度缓存"
            else:
                status = "failed"
                message = f"错误：cached={cached1}, text={'有内容' if text1 else '空'}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_2",
                test_name=test_name,
                status=status,
                expected="cached=False, 创建低精度缓存",
                actual=f"cached={cached1}, text_length={len(text1) if text1 else 0}",
                message=message,
                duration=duration,
                image_path=image_path
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_2",
                test_name=test_name,
                status="error",
                expected="执行成功",
                actual=f"错误: {e}",
                message=f"测试失败: {e}",
                duration=duration
            )
    
    def _test_cache_scenario_3_3(self, image_path: str) -> TestResult:
        """场景3.3：低精度缓存，要求高精度"""
        test_name = "缓存测试-场景3.3：低精度缓存，要求高精度"
        start_time = time.time()
        
        try:
            # 清理缓存
            clear_image_cache(self.engine, image_path)
            
            # 先创建低精度缓存
            text1, cached1 = self.engine.get_text(image_path, use_cache=True, is_precise=False)
            
            # 要求高精度
            text2, cached2 = self.engine.get_text(image_path, use_cache=True, is_precise=True)
            
            # 验证：应该重新识别（cached=False），因为需要升级
            if not cached2 and text2:
                status = "passed"
                message = "正确：低精度缓存存在，要求高精度时重新识别并升级缓存"
            else:
                status = "failed"
                message = f"错误：cached2={cached2}, 应该为False以触发高精度识别"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_3",
                test_name=test_name,
                status=status,
                expected="cached2=False, 使用高精度OCR重新识别",
                actual=f"cached1={cached1}, cached2={cached2}",
                message=message,
                duration=duration,
                image_path=image_path
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_3",
                test_name=test_name,
                status="error",
                expected="执行成功",
                actual=f"错误: {e}",
                message=f"测试失败: {e}",
                duration=duration
            )
    
    def _test_cache_scenario_3_4(self, image_path: str) -> TestResult:
        """场景3.4：高精度缓存，要求高精度"""
        test_name = "缓存测试-场景3.4：高精度缓存，要求高精度"
        start_time = time.time()
        
        try:
            # 清理缓存
            clear_image_cache(self.engine, image_path)
            
            # 先创建高精度缓存
            text1, cached1 = self.engine.get_text(image_path, use_cache=True, is_precise=True)
            
            # 再次要求高精度
            text2, cached2 = self.engine.get_text(image_path, use_cache=True, is_precise=True)
            
            # 验证：应该命中缓存
            if cached2 and text1 == text2:
                status = "passed"
                message = "正确：高精度缓存命中，直接返回缓存结果"
            else:
                status = "failed"
                message = f"错误：cached2={cached2}, 文本是否相同={text1 == text2}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_4",
                test_name=test_name,
                status=status,
                expected="cached2=True, 文本相同",
                actual=f"cached1={cached1}, cached2={cached2}, text_same={text1 == text2}",
                message=message,
                duration=duration,
                image_path=image_path
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_4",
                test_name=test_name,
                status="error",
                expected="执行成功",
                actual=f"错误: {e}",
                message=f"测试失败: {e}",
                duration=duration
            )
    
    def _test_cache_scenario_3_5(self, image_path: str) -> TestResult:
        """场景3.5：高精度缓存，要求低精度"""
        test_name = "缓存测试-场景3.5：高精度缓存，要求低精度"
        start_time = time.time()
        
        try:
            # 清理缓存
            clear_image_cache(self.engine, image_path)
            
            # 先创建高精度缓存
            text1, cached1 = self.engine.get_text(image_path, use_cache=True, is_precise=True)
            
            # 要求低精度
            text2, cached2 = self.engine.get_text(image_path, use_cache=True, is_precise=False)
            
            # 验证：应该命中缓存（虽然精度更高但可用）
            if cached2 and text1 == text2:
                status = "passed"
                message = "正确：高精度缓存可用，直接返回缓存结果"
            else:
                status = "failed"
                message = f"错误：cached2={cached2}, 文本是否相同={text1 == text2}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_5",
                test_name=test_name,
                status=status,
                expected="cached2=True, 文本相同",
                actual=f"cached1={cached1}, cached2={cached2}, text_same={text1 == text2}",
                message=message,
                duration=duration,
                image_path=image_path
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_5",
                test_name=test_name,
                status="error",
                expected="执行成功",
                actual=f"错误: {e}",
                message=f"测试失败: {e}",
                duration=duration
            )
    
    def _test_cache_scenario_3_6(self, image_path: str) -> TestResult:
        """场景3.6：低精度缓存，要求低精度"""
        test_name = "缓存测试-场景3.6：低精度缓存，要求低精度"
        start_time = time.time()
        
        try:
            # 清理缓存
            clear_image_cache(self.engine, image_path)
            
            # 先创建低精度缓存
            text1, cached1 = self.engine.get_text(image_path, use_cache=True, is_precise=False)
            
            # 再次要求低精度
            text2, cached2 = self.engine.get_text(image_path, use_cache=True, is_precise=False)
            
            # 验证：应该命中缓存
            if cached2 and text1 == text2:
                status = "passed"
                message = "正确：低精度缓存命中，直接返回缓存结果"
            else:
                status = "failed"
                message = f"错误：cached2={cached2}, 文本是否相同={text1 == text2}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_6",
                test_name=test_name,
                status=status,
                expected="cached2=True, 文本相同",
                actual=f"cached1={cached1}, cached2={cached2}, text_same={text1 == text2}",
                message=message,
                duration=duration,
                image_path=image_path
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_6",
                test_name=test_name,
                status="error",
                expected="执行成功",
                actual=f"错误: {e}",
                message=f"测试失败: {e}",
                duration=duration
            )
    
    def _test_cache_scenario_3_7(self, image_path: str) -> TestResult:
        """场景3.7：禁用缓存测试"""
        test_name = "缓存测试-场景3.7：禁用缓存"
        start_time = time.time()
        
        try:
            # 清理缓存
            clear_image_cache(self.engine, image_path)
            
            # 禁用缓存，第一次调用
            text1, cached1 = self.engine.get_text(image_path, use_cache=False, is_precise=True)
            
            # 禁用缓存，第二次调用
            text2, cached2 = self.engine.get_text(image_path, use_cache=False, is_precise=True)
            
            # 验证：两次都应该返回cached=False
            if not cached1 and not cached2 and text1 and text2:
                status = "passed"
                message = "正确：禁用缓存时，两次调用都执行OCR，不读取缓存"
            else:
                status = "failed"
                message = f"错误：cached1={cached1}, cached2={cached2}"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_7",
                test_name=test_name,
                status=status,
                expected="cached1=False, cached2=False",
                actual=f"cached1={cached1}, cached2={cached2}",
                message=message,
                duration=duration,
                image_path=image_path
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_3_7",
                test_name=test_name,
                status="error",
                expected="执行成功",
                actual=f"错误: {e}",
                message=f"测试失败: {e}",
                duration=duration
            )
    
    def test_image_preprocessing(self) -> TestResult:
        """测试用例4：图片预处理测试"""
        test_name = "图片预处理测试"
        start_time = time.time()
        
        # 选择一个图片文件
        test_image = None
        for file_info in self.test_files:
            if file_info["type"] in ["award", "other"]:
                test_image = file_info
                break
        
        if not test_image:
            return TestResult(
                test_case="test_4",
                test_name=test_name,
                status="error",
                expected="测试图片预处理",
                actual="未找到测试图片",
                message="测试文件缺失",
                duration=time.time() - start_time
            )
        
        try:
            image_path = test_image["full_path"]
            original_size = get_image_size(image_path)
            
            # 执行OCR（会自动预处理）
            text, cached = self.engine.get_text(image_path, use_cache=False, is_precise=True)
            
            # 检查是否有预处理日志或临时文件
            # 注意：由于预处理在内部进行，我们主要通过验证OCR成功来间接验证预处理
            if text:
                status = "passed"
                message = f"预处理成功，原始尺寸: {original_size[0]}×{original_size[1]}"
            else:
                status = "failed"
                message = "预处理或OCR失败"
            
            duration = time.time() - start_time
            return TestResult(
                test_case="test_4",
                test_name=test_name,
                status=status,
                expected="图片预处理成功，OCR识别成功",
                actual=message,
                message=message,
                duration=duration,
                image_path=image_path
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_case="test_4",
                test_name=test_name,
                status="error",
                expected="预处理测试成功",
                actual=f"错误: {e}",
                message=f"测试失败: {e}",
                duration=duration
            )
    
    def test_ocr_quality(self) -> List[TestResult]:
        """测试用例5：OCR识别效果测试"""
        results = []
        
        for file_info in self.test_files:
            test_name = f"OCR识别效果测试-{file_info['name']}"
            start_time = time.time()
            
            try:
                file_path = file_info["full_path"]
                
                # 高精度识别
                precise_text, precise_cached = self.engine.get_text(
                    file_path, use_cache=False, is_precise=True
                )
                precise_time = time.time() - start_time
                
                # 低精度识别
                fast_start = time.time()
                fast_text, fast_cached = self.engine.get_text(
                    file_path, use_cache=False, is_precise=False
                )
                fast_time = time.time() - fast_start
                
                # 计算相似度
                similarity = calculate_similarity(precise_text or "", fast_text or "")
                
                status = "passed" if precise_text or fast_text else "failed"
                message = f"高精度: {len(precise_text) if precise_text else 0}字符, "
                message += f"低精度: {len(fast_text) if fast_text else 0}字符, "
                message += f"相似度: {similarity:.3f}"
                
                duration = time.time() - start_time
                results.append(TestResult(
                    test_case=f"test_5_{file_info['type']}",
                    test_name=test_name,
                    status=status,
                    expected="识别成功，返回文本",
                    actual=message,
                    message=message,
                    duration=duration,
                    image_path=file_path,
                    precise_result=precise_text,
                    fast_result=fast_text
                ))
            except Exception as e:
                duration = time.time() - start_time
                results.append(TestResult(
                    test_case=f"test_5_{file_info['type']}",
                    test_name=test_name,
                    status="error",
                    expected="识别成功",
                    actual=f"错误: {e}",
                    message=f"测试失败: {e}",
                    duration=duration,
                    image_path=file_info.get("full_path")
                ))
        
        return results
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始OCR功能测试")
        
        # 测试用例1：文件路径错误
        logger.info("执行测试用例1：文件路径错误测试")
        self.results.append(self.test_file_not_found())
        
        # 测试用例2：PDF处理
        logger.info("执行测试用例2：PDF文件识别测试")
        self.results.append(self.test_pdf_processing())
        
        # 测试用例3：缓存测试
        logger.info("执行测试用例3：缓存命中测试")
        self.results.extend(self.test_cache_scenarios())
        
        # 测试用例4：图片预处理
        logger.info("执行测试用例4：图片预处理测试")
        self.results.append(self.test_image_preprocessing())
        
        # 测试用例5：OCR识别效果
        logger.info("执行测试用例5：OCR识别效果测试")
        self.results.extend(self.test_ocr_quality())
        
        logger.info(f"所有测试完成，共 {len(self.results)} 个测试用例")
    
    def generate_html_report(self, output_path: str):
        """生成HTML测试报告"""
        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        errors = sum(1 for r in self.results if r.status == "error")
        total = len(self.results)
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCR功能测试报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.9; font-size: 0.95em; }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .summary-card .number {{
            font-size: 2.5em;
            font-weight: bold;
        }}
        .summary-card.passed .number {{ color: #28a745; }}
        .summary-card.failed .number {{ color: #dc3545; }}
        .summary-card.error .number {{ color: #ffc107; }}
        .summary-card.total .number {{ color: #667eea; }}
        .summary-card .label {{
            color: #6c757d;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .test-item {{
            border-bottom: 1px solid #e9ecef;
            padding: 30px;
        }}
        .test-item:last-child {{ border-bottom: none; }}
        .test-header {{
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }}
        .test-status {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 15px;
        }}
        .test-status.passed {{ background: #28a745; }}
        .test-status.failed {{ background: #dc3545; }}
        .test-status.error {{ background: #ffc107; }}
        .test-title {{
            font-size: 1.3em;
            color: #333;
            flex: 1;
        }}
        .test-info {{
            color: #6c757d;
            font-size: 0.9em;
        }}
        .test-details {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-top: 15px;
        }}
        .test-details table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .test-details td {{
            padding: 8px 12px;
            border-bottom: 1px solid #e9ecef;
        }}
        .test-details td:first-child {{
            font-weight: 600;
            color: #495057;
            width: 150px;
        }}
        .image-preview {{
            text-align: center;
            margin: 20px 0;
        }}
        .image-preview img {{
            max-width: 100%;
            max-height: 400px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .ocr-results {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }}
        .ocr-result-card {{
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            background: white;
        }}
        .ocr-result-card h4 {{
            margin-bottom: 10px;
            color: #667eea;
        }}
        .ocr-text {{
            white-space: pre-wrap;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
            max-height: 300px;
            overflow-y: auto;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OCR功能测试报告</h1>
            <div class="meta">
                生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
                测试用例数: {total}
            </div>
        </div>
        
        <div class="summary">
            <div class="summary-card total">
                <div class="number">{total}</div>
                <div class="label">总测试数</div>
            </div>
            <div class="summary-card passed">
                <div class="number">{passed}</div>
                <div class="label">通过</div>
            </div>
            <div class="summary-card failed">
                <div class="number">{failed}</div>
                <div class="label">失败</div>
            </div>
            <div class="summary-card error">
                <div class="number">{errors}</div>
                <div class="label">错误</div>
            </div>
            <div class="summary-card">
                <div class="number" style="color: #667eea;">{passed/total*100:.1f}%</div>
                <div class="label">通过率</div>
            </div>
        </div>
"""
        
        # 生成每个测试用例的结果
        for idx, result in enumerate(self.results, 1):
            status_class = result.status
            status_icon = "✓" if status_class == "passed" else "✗" if status_class == "failed" else "!"
            
            html += f"""
        <div class="test-item">
            <div class="test-header">
                <div class="test-status {status_class}"></div>
                <div class="test-title">
                    {idx}. {result.test_name}
                </div>
                <div class="test-info">
                    {status_icon} {result.status.upper()} | 耗时: {result.duration:.3f}s
                </div>
            </div>
            
            <div class="test-details">
                <table>
                    <tr>
                        <td>测试用例ID</td>
                        <td>{result.test_case}</td>
                    </tr>
                    <tr>
                        <td>预期结果</td>
                        <td>{result.expected}</td>
                    </tr>
                    <tr>
                        <td>实际结果</td>
                        <td>{result.actual}</td>
                    </tr>
                    <tr>
                        <td>测试消息</td>
                        <td>{result.message}</td>
                    </tr>
"""
            
            # 如果有图片，显示图片预览
            if result.image_path and Path(result.image_path).exists():
                img_b64 = image_to_base64(result.image_path)
                if img_b64:
                    html += f"""
                    <tr>
                        <td>测试图片</td>
                        <td>
                            <div class="image-preview">
                                <img src="data:image/jpeg;base64,{img_b64}" alt="测试图片">
                            </div>
                        </td>
                    </tr>
"""
            
            # 如果有OCR结果，显示对比
            if result.precise_result or result.fast_result:
                html += """
                    <tr>
                        <td>识别结果对比</td>
                        <td>
                            <div class="ocr-results">
"""
                if result.precise_result:
                    html += f"""
                                <div class="ocr-result-card">
                                    <h4>高精度OCR</h4>
                                    <div class="ocr-text">{result.precise_result[:500]}{'...' if len(result.precise_result) > 500 else ''}</div>
                                </div>
"""
                if result.fast_result:
                    html += f"""
                                <div class="ocr-result-card">
                                    <h4>低精度OCR</h4>
                                    <div class="ocr-text">{result.fast_result[:500]}{'...' if len(result.fast_result) > 500 else ''}</div>
                                </div>
"""
                html += """
                            </div>
                        </td>
                    </tr>
"""
            
            html += """
                </table>
            </div>
        </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        
        # 写入文件
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path_obj, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"HTML报告已保存到: {output_path}")


def main():
    """主程序"""
    print("="*60)
    print("OCR功能测试程序")
    print("="*60)
    print()
    
    tester = OCRTester()
    
    # 初始化
    if not tester.setup():
        print("初始化失败，退出测试")
        return
    
    print(f"加载了 {len(tester.test_files)} 个测试文件")
    print()
    
    # 运行所有测试
    try:
        tester.run_all_tests()
        
        # 生成报告
        report_path = project_root / "tests" / "reports" / "ocr功能测试报告.html"
        tester.generate_html_report(str(report_path))
        
        # 输出摘要
        passed = sum(1 for r in tester.results if r.status == "passed")
        failed = sum(1 for r in tester.results if r.status == "failed")
        errors = sum(1 for r in tester.results if r.status == "error")
        total = len(tester.results)
        
        print()
        print("="*60)
        print("测试完成")
        print("="*60)
        print(f"总测试数: {total}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"错误: {errors}")
        print(f"通过率: {passed/total*100:.1f}%")
        print()
        print(f"详细报告已保存到:")
        print(f"  {report_path}")
        print()
        print("正在打开浏览器显示测试报告...")
        
        # 自动打开浏览器显示报告
        try:
            # 转换为绝对路径
            report_path_abs = Path(report_path).resolve()
            # 使用 file:// 协议打开本地文件
            report_url = f"file:///{report_path_abs.as_posix()}"
            webbrowser.open(report_url)
            print("浏览器已打开测试报告")
        except Exception as e:
            print(f"无法自动打开浏览器: {e}")
            print("请手动在浏览器中打开以下文件:")
            print(f"  {report_path}")
        
    except Exception as e:
        print(f"\n测试执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
