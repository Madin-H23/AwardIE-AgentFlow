"""Manual Import Service 单元测试（pytest 函数式，T31-T34 批次3 转换）。"""
from unittest.mock import Mock

import pytest

from backend.services.manual_import_service import ManualImportService
from backend.extract.types import ExtractResult, ExtractStatus


@pytest.fixture()
def service():
    """构造全 mock 依赖的 ManualImportService。"""
    framework = Mock()
    ocr_engine = Mock()
    framework.ocr_engine = ocr_engine
    llm_engine = Mock()
    framework.llm_engine = llm_engine

    award_extractor = Mock()
    award_extractor.name = "award"
    patent_extractor = Mock()
    patent_extractor.name = "patent"
    software_extractor = Mock()
    software_extractor.name = "software"
    framework._extractors = [award_extractor, patent_extractor, software_extractor]

    svc = ManualImportService(framework)
    svc._mocks = {
        "framework": framework,
        "ocr": ocr_engine,
        "llm": llm_engine,
        "award_extractor": award_extractor,
    }
    return svc


def test_initialization(service):
    assert service is not None
    assert service.framework == service._mocks["framework"]
    assert service.ocr_engine == service._mocks["ocr"]
    assert service.llm_engine == service._mocks["llm"]


def test_get_extractor_by_type_award(service):
    assert service._get_extractor_by_type("award").name == "award"


def test_get_extractor_by_type_patent(service):
    assert service._get_extractor_by_type("patent").name == "patent"


def test_get_extractor_by_type_software(service):
    assert service._get_extractor_by_type("software").name == "software"


def test_get_extractor_by_type_invalid(service):
    with pytest.raises(ValueError) as ctx:
        service._get_extractor_by_type("invalid")
    assert "不支持的类型" in str(ctx.value)


def test_parse_by_type_ocr_success(service):
    mocks = service._mocks
    test_ocr_text = "获奖证书\n一等奖\n张三"
    mocks["ocr"].get_text.return_value = (test_ocr_text, False)
    mocks["award_extractor"].extract.return_value = ExtractResult(
        status=ExtractStatus.SUCCESS,
        data={"competition_name": "测试竞赛", "award_level": "一等奖"},
        template_type="award",
        extractor_name="award",
        ocr_text=test_ocr_text)

    result = service.parse_by_type("/fake/path/award.jpg", "award")

    assert result.status == ExtractStatus.SUCCESS
    assert result.template_type == "award"
    assert result.data["competition_name"] == "测试竞赛"
    mocks["ocr"].get_text.assert_called_once()
    mocks["award_extractor"].extract.assert_called_once()


def test_parse_by_type_ocr_failure(service):
    service._mocks["ocr"].get_text.side_effect = Exception("OCR failed")
    result = service.parse_by_type("/fake/path/award.jpg", "award")
    assert result.status == "ocr_error"
    assert "OCR识别失败" in result.error_message


def test_parse_by_type_ocr_empty_text(service):
    service._mocks["ocr"].get_text.return_value = (None, False)
    result = service.parse_by_type("/fake/path/award.jpg", "award")
    assert result.status == "ocr_error"
    assert "OCR未能识别出文本" in result.error_message


def test_parse_by_type_invalid_type(service):
    service._mocks["ocr"].get_text.return_value = ("test text", False)
    result = service.parse_by_type("/fake/path/test.jpg", "invalid")
    assert result.status == "error"
    assert "不支持的类型" in result.error_message


def test_get_supported_types(service):
    assert sorted(service.get_supported_types()) == ["award", "patent", "software"]


def test_parse_by_type_extractor_exception(service):
    mocks = service._mocks
    mocks["ocr"].get_text.return_value = ("获奖证书\n一等奖\n张三", False)
    mocks["award_extractor"].extract.side_effect = Exception("Extractor failed")
    result = service.parse_by_type("/fake/path/award.jpg", "award")
    assert result.status == "error"
    assert "抽取失败" in result.error_message
