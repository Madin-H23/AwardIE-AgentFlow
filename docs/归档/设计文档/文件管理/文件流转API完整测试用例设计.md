> ⚠️ 已归档（2026-08-24）：本文档为历史资料，不反映项目现状。现行权威文档见 docs/README.md 路由。

# 文件流转API完整测试用例设计

## 1. 测试目标

通过Flask API调用，完整覆盖文件管理模块的所有使用场景，包括：
1. 各类成果（奖状、专利、软著）的图片/文件查看
2. 编辑页面中的文件显示
3. 实验室图片和下载文件的上传、查看、删除
4. 其他文件的查看和编辑
5. 文件导入过程中的文件访问

## 2. 已测试的API（当前测试覆盖）

### 2.1 文件上传与审核流程
- ✅ `POST /admin/file-import/upload` - 文件上传
- ✅ `POST /admin/file-import/award-submit/<session_id>/<index>` - 奖状提交审核
- ✅ `POST /admin/file-import/api/submit` - 通用提交审核
- ✅ `POST /admin/api/achievement-review/<pending_id>/approve-with-data` - 审核通过
- ✅ `POST /admin/file-import/api/other/submit` - 其他类型提交到实验室

### 2.2 文件查看/下载（部分已测试）
- ✅ `GET /admin/awards/<award_id>/image` - 奖状图片查看（已测试）
- ✅ `GET /admin/patents/<patent_id>/file` - 专利证书下载（已测试）
- ✅ `GET /admin/software/<copyright_id>/file` - 软著证书下载（已测试）
- ✅ `GET /admin/laboratories/<lab_id>/downloads/<download_id>/file` - 实验室下载文件（已测试）

## 3. 需要补充测试的API

### 3.1 编辑页面中的文件显示

#### 3.1.1 奖状编辑页面
- **API**: `GET /admin/awards/<award_id>/edit`
- **功能**: 编辑页面显示，页面中会调用 `/admin/awards/<award_id>/image` 显示图片
- **测试点**:
  - 编辑页面可以正常访问
  - 页面中的图片URL可以正常访问
  - 图片显示正确

#### 3.1.2 专利编辑页面
- **API**: `GET /admin/patents/<patent_id>/edit`
- **功能**: 编辑页面显示，页面中会调用 `/admin/patents/<patent_id>/file` 显示文件
- **测试点**:
  - 编辑页面可以正常访问
  - 文件下载链接可以正常访问
  - 文件可以正常下载

#### 3.1.3 软著编辑页面
- **API**: `GET /admin/software/<copyright_id>/edit`
- **功能**: 编辑页面显示，页面中会调用 `/admin/software/<copyright_id>/file` 显示文件
- **测试点**:
  - 编辑页面可以正常访问
  - 文件下载链接可以正常访问
  - 文件可以正常下载

### 3.2 实验室图片管理

#### 3.2.1 上传实验室图片
- **API**: `POST /admin/laboratories/<lab_id>/images/upload`
- **功能**: 上传图片到实验室相册
- **参数**: 
  - `image`: 图片文件（multipart/form-data）
- **返回**: 
  - `success`: 是否成功
  - `message`: 消息
  - `image_path`: 图片路径
- **文件位置**: `laboratories/{lab_id}/photos/{filename}`
- **测试点**:
  - 上传成功，返回正确的image_path
  - 文件保存在正确的位置
  - 数据库中有新记录

#### 3.2.2 查看实验室图片
- **API**: `GET /admin/files/laboratory/<filename>`
- **功能**: 查看实验室图片（公开访问）
- **参数**: 
  - `filename`: 文件名或相对路径
- **返回**: 图片文件（send_file）
- **测试点**:
  - 可以通过文件名访问
  - 可以通过完整相对路径访问
  - 返回正确的MIME类型
  - 图片内容正确

#### 3.2.3 删除实验室图片
- **API**: `POST /admin/laboratories/<lab_id>/images/delete`
- **功能**: 删除实验室图片
- **参数** (JSON):
  - `image_path`: 图片路径
- **返回**: 
  - `success`: 是否成功
  - `message`: 消息
- **测试点**:
  - 删除成功
  - 文件从文件系统删除
  - 数据库记录删除

### 3.3 实验室下载专区管理

#### 3.3.1 上传下载文件
- **API**: `POST /admin/laboratories/<lab_id>/downloads/upload`
- **功能**: 上传文件到实验室下载专区
- **参数**: 
  - `file`: 文件（multipart/form-data）
  - `file_title`: 文件标题（可选）
  - `is_public`: 是否公开（可选，默认true）
- **返回**: 
  - `success`: 是否成功
  - `message`: 消息
  - `file_path`: 文件路径
- **文件位置**: `laboratories/{lab_id}/downloads/{filename}`
- **测试点**:
  - 上传成功，返回正确的file_path
  - 文件保存在正确的位置
  - 数据库中有新记录

#### 3.3.2 删除下载文件
- **API**: `DELETE /admin/laboratories/<lab_id>/downloads/<download_id>`
- **功能**: 删除实验室下载专区的文件
- **返回**: 
  - `success`: 是否成功
  - `message`: 消息
- **测试点**:
  - 删除成功
  - 文件从文件系统删除
  - 数据库记录删除

### 3.4 其他文件管理

#### 3.4.1 查看其他文件详情
- **API**: `GET /admin/other-files/<file_id>`
- **功能**: 查看文件详情页面
- **测试点**:
  - 页面可以正常访问
  - 文件信息显示正确
  - 下载链接可以正常访问

#### 3.4.2 下载其他文件
- **API**: `GET /admin/other-files/<file_id>/download`
- **功能**: 下载其他文件
- **测试点**:
  - 文件可以正常下载
  - 返回正确的文件名
  - 文件内容正确

#### 3.4.3 编辑其他文件
- **API**: `POST /admin/other-files/<file_id>/edit`
- **功能**: 编辑文件元数据
- **参数**: 
  - `file_name`: 文件名
  - `description`: 描述（可选）
  - `laboratory_id`: 实验室ID（可选）
- **测试点**:
  - 编辑成功
  - 数据库记录更新
  - 文件路径不变

### 3.5 文件导入过程中的文件访问

#### 3.5.1 查看导入中的文件
- **API**: `GET /admin/file-import/file/<file_path>`
- **功能**: 提供文件导入过程中的文件访问
- **参数**: 
  - `file_path`: 相对路径（如 `temp_upload/{session_id}/{hash}.ext`）
- **返回**: 文件内容（send_file）
- **测试点**:
  - 可以访问temp_upload中的文件
  - 可以访问review中的文件
  - 返回正确的MIME类型
  - 文件内容正确

## 4. 测试用例详细设计

### 测试用例1: 奖状编辑页面图片显示

**前置条件**: 已有一个审核通过的奖状记录

**步骤**:
1. 调用 `GET /admin/awards/<award_id>/edit` 获取编辑页面
2. 从页面HTML中提取图片URL（通常是 `/admin/awards/<award_id>/image`）
3. 调用图片URL验证图片可访问
4. 验证图片内容正确

**验证点**:
- 编辑页面返回200
- 图片URL存在且可访问
- 图片Content-Type正确
- 图片内容长度 > 0

### 测试用例2: 专利编辑页面文件显示

**前置条件**: 已有一个审核通过的专利记录

**步骤**:
1. 调用 `GET /admin/patents/<patent_id>/edit` 获取编辑页面
2. 从页面HTML中提取文件下载URL（通常是 `/admin/patents/<patent_id>/file`）
3. 调用文件URL验证文件可下载
4. 验证文件内容正确

**验证点**:
- 编辑页面返回200
- 文件URL存在且可下载
- 文件Content-Type正确
- 文件内容长度 > 0

### 测试用例3: 软著编辑页面文件显示

**前置条件**: 已有一个审核通过的软著记录

**步骤**: 同测试用例2（专利）

### 测试用例4: 实验室图片上传、查看、删除

**步骤**:
1. **上传图片**: 调用 `POST /admin/laboratories/<lab_id>/images/upload` 上传测试图片
2. **验证上传**: 
   - 响应 `success=True`
   - 返回 `image_path`
   - 文件存在于 `laboratories/{lab_id}/photos/`
   - 数据库中有新记录
3. **查看图片**: 调用 `GET /admin/files/laboratory/<filename>` 验证图片可访问
4. **删除图片**: 调用 `POST /admin/laboratories/<lab_id>/images/delete` 删除图片
5. **验证删除**: 
   - 响应 `success=True`
   - 文件从文件系统删除
   - 数据库记录删除

**验证点**:
- 上传成功，文件位置正确
- 图片可以正常访问
- 删除成功，文件已删除

### 测试用例5: 实验室下载文件上传、查看、删除

**步骤**:
1. **上传文件**: 调用 `POST /admin/laboratories/<lab_id>/downloads/upload` 上传测试文件
2. **验证上传**: 
   - 响应 `success=True`
   - 返回 `file_path`
   - 文件存在于 `laboratories/{lab_id}/downloads/`
   - 数据库中有新记录
3. **查看文件**: 调用 `GET /admin/laboratories/<lab_id>/downloads/<download_id>/file` 验证文件可下载
4. **删除文件**: 调用 `DELETE /admin/laboratories/<lab_id>/downloads/<download_id>` 删除文件
5. **验证删除**: 
   - 响应 `success=True`
   - 文件从文件系统删除
   - 数据库记录删除

**验证点**:
- 上传成功，文件位置正确
- 文件可以正常下载
- 删除成功，文件已删除

### 测试用例6: 其他文件查看和编辑

**前置条件**: 已有一个其他文件记录（通过文件导入流程创建）

**步骤**:
1. **查看文件详情**: 调用 `GET /admin/other-files/<file_id>` 获取详情页面
2. **验证详情**: 
   - 页面返回200
   - 文件信息显示正确
3. **下载文件**: 调用 `GET /admin/other-files/<file_id>/download` 下载文件
4. **验证下载**: 
   - 文件可以正常下载
   - 文件内容正确
5. **编辑文件**: 调用 `POST /admin/other-files/<file_id>/edit` 更新文件信息
6. **验证编辑**: 
   - 响应成功
   - 数据库记录更新
   - 文件路径不变

**验证点**:
- 详情页面可访问
- 文件可以正常下载
- 编辑成功，数据更新

### 测试用例7: 文件导入过程中的文件访问

**前置条件**: 已上传文件但未提交审核（文件在temp_upload目录）

**步骤**:
1. **访问temp_upload文件**: 调用 `GET /admin/file-import/file/temp_upload/{session_id}/{hash}.ext`
2. **验证访问**: 
   - 返回200
   - 文件内容正确
   - MIME类型正确
3. **提交审核后访问review文件**: 提交审核后，调用 `GET /admin/file-import/file/review/{session_id}/{hash}.ext`
4. **验证访问**: 
   - 返回200
   - 文件内容正确
   - MIME类型正确

**验证点**:
- temp_upload中的文件可以访问
- review中的文件可以访问
- 文件内容正确

## 5. 测试实现要点

### 5.1 编辑页面HTML解析

```python
from bs4 import BeautifulSoup

def extract_image_url_from_edit_page(html_content):
    """从编辑页面HTML中提取图片URL"""
    soup = BeautifulSoup(html_content, 'html.parser')
    # 查找img标签或包含图片URL的元素
    img_tag = soup.find('img', {'id': 'award-image'}) or soup.find('img', src=True)
    if img_tag:
        return img_tag.get('src')
    return None
```

### 5.2 实验室图片上传

```python
def test_lab_image_upload(self, lab_id, image_path):
    """测试实验室图片上传"""
    with open(image_path, 'rb') as f:
        response = self.client.post(
            f'/admin/laboratories/{lab_id}/images/upload',
            data={'image': (f, 'test.jpg')},
            content_type='multipart/form-data'
        )
    return response
```

### 5.3 文件删除验证

```python
def verify_file_deleted(self, file_path):
    """验证文件已删除"""
    file_manager = get_unified_file_manager()
    try:
        full_path = file_manager.find_file_by_path(file_path)
        return not full_path.exists()
    except FileNotFoundError:
        return True  # 文件不存在，说明已删除
```

## 6. 测试数据准备

### 6.1 测试文件
- 奖状图片: `images/测试图片/奖状/2024支付宝小程序国家二等奖.jpg`
- 专利图片: `images/测试图片/专利/1721722613444187.jpg`
- 软著图片: `images/测试图片/软著/1.jpg`
- 其他图片: `images/测试图片/其他/2025.jpg`
- 实验室测试图片: 使用其他图片或创建新的测试图片

### 6.2 数据库清理（可选）
如果需要清空数据库进行测试：
- 保留表: `award_templates`, `students`, `teachers`, `admins`, `ocr_cache`, `llm_cache`
- 清空表: `awards`, `patents`, `software_copyrights`, `innovation_projects`, `other_files`, `pending_achievements`, `laboratory_images`, `laboratory_downloads`

## 7. 测试执行顺序

1. **基础流程测试**（已有）:
   - 奖状、专利、软著、其他、大创的完整流转

2. **编辑页面测试**:
   - 奖状编辑页面图片显示
   - 专利编辑页面文件显示
   - 软著编辑页面文件显示

3. **实验室功能测试**:
   - 实验室图片上传、查看、删除
   - 实验室下载文件上传、查看、删除

4. **其他文件测试**:
   - 其他文件查看、下载、编辑

5. **文件导入过程测试**:
   - temp_upload文件访问
   - review文件访问

## 8. 预期测试结果

- **编辑页面**: 所有编辑页面可以正常访问，文件/图片可以正常显示
- **实验室功能**: 图片和文件的上传、查看、删除功能正常
- **其他文件**: 查看、下载、编辑功能正常
- **文件导入过程**: 临时文件可以正常访问

## 9. 实施计划

1. **阶段1**: 实现编辑页面测试用例（奖状、专利、软著）
2. **阶段2**: 实现实验室功能测试用例（图片和下载文件）
3. **阶段3**: 实现其他文件测试用例
4. **阶段4**: 实现文件导入过程测试用例
5. **阶段5**: 整合所有测试用例，生成完整测试报告

---
**文档状态**: 设计完成，待实施
**创建时间**: 2026-01-25
**最后更新**: 2026-01-25
