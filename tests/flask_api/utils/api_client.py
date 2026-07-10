"""
Flask API 测试客户端
模拟用户操作，封装HTTP请求
"""
import requests
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class FlaskAPIClient:
    """Flask API 客户端，模拟用户操作"""

    def __init__(self, base_url: str = "http://127.0.0.1:5001"):
        """
        初始化客户端

        Args:
            base_url: Flask服务器地址
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.cookies.clear()

        # 记录当前用户信息
        self.current_user = None
        self.current_user_type = None

        # 记录捕获的变量（如pending_id, award_id等）
        self.captured_vars = {}

        logger.info(f"FlaskAPIClient initialized for {base_url}")

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        用户登录

        Args:
            username: 用户名/学号/工号
            password: 密码

        Returns:
            (是否成功, 错误信息)
        """
        url = f"{self.base_url}/login"
        data = {
            'username': username,
            'password': password,
            'remember': 'false'
        }

        try:
            response = self.session.post(url, data=data, allow_redirects=False)
            logger.info(f"Login attempt for {username}: status={response.status_code}")

            if response.status_code in [302, 303]:
                # 登录成功（重定向）
                self.current_user = username
                # 通过API获取用户类型
                user_info = self.get_user_info()
                if user_info:
                    self.current_user_type = user_info.get('user_type')
                logger.info(f"Login successful: {username}, type={self.current_user_type}")
                return True, ""
            elif response.status_code == 200:
                # 登录失败，返回登录页面
                return False, "登录失败，请检查用户名和密码"
            else:
                return False, f"Unexpected status code: {response.status_code}"

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False, str(e)

    def logout(self) -> bool:
        """用户登出"""
        url = f"{self.base_url}/logout"
        try:
            response = self.session.get(url, allow_redirects=False)
            self.current_user = None
            self.current_user_type = None
            self.session.cookies.clear()
            logger.info("Logout successful")
            return response.status_code in [302, 303]
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False

    def get(self, endpoint: str, params: Optional[Dict] = None,
            expect_json: bool = False) -> Tuple[bool, Any]:
        """
        GET 请求

        Args:
            endpoint: API端点（如 /admin/awards）
            params: 查询参数
            expect_json: 是否期望JSON响应

        Returns:
            (是否成功, 响应数据或错误信息)
        """
        url = f"{self.base_url}{endpoint}"
        headers = {'Accept': 'application/json'} if expect_json else {}

        try:
            response = self.session.get(url, params=params, headers=headers)
            logger.info(f"GET {endpoint}: status={response.status_code}")

            if response.status_code == 200:
                if expect_json:
                    try:
                        return True, response.json()
                    except:
                        return True, response.text
                return True, response.text
            else:
                return False, f"Status code: {response.status_code}"

        except Exception as e:
            logger.error(f"GET {endpoint} error: {e}")
            return False, str(e)

    def post(self, endpoint: str, data: Optional[Dict] = None,
             files: Optional[Dict] = None) -> Tuple[bool, Any]:
        """
        POST 请求

        Args:
            endpoint: API端点
            data: 表单数据
            files: 上传的文件

        Returns:
            (是否成功, 响应数据或错误信息)
        """
        url = f"{self.base_url}{endpoint}"

        try:
            if files:
                response = self.session.post(url, data=data, files=files)
            else:
                headers = {'Content-Type': 'application/json'}
                json_data = json.dumps(data) if data else None
                response = self.session.post(url, data=json_data,
                                               headers=headers)

            logger.info(f"POST {endpoint}: status={response.status_code}")

            if response.status_code in [200, 201]:
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                error_msg = f"Status code: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f", detail: {error_detail}"
                except:
                    pass
                return False, error_msg

        except Exception as e:
            logger.error(f"POST {endpoint} error: {e}")
            return False, str(e)

    def delete(self, endpoint: str) -> Tuple[bool, Any]:
        """DELETE 请求"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.delete(url)
            logger.info(f"DELETE {endpoint}: status={response.status_code}")

            if response.status_code == 200:
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                return False, f"Status code: {response.status_code}"

        except Exception as e:
            logger.error(f"DELETE {endpoint} error: {e}")
            return False, str(e)

    def upload_file(self, endpoint: str, file_path: str,
                    additional_data: Optional[Dict] = None) -> Tuple[bool, Any]:
        """
        上传文件

        Args:
            endpoint: API端点
            file_path: 文件路径
            additional_data: 额外的表单数据

        Returns:
            (是否成功, 响应数据)
        """
        path = Path(file_path)
        if not path.exists():
            return False, f"File not found: {file_path}"

        files = {'file': (path.name, open(path, 'rb'))}
        data = additional_data or {}

        try:
            success, result = self.post(endpoint, data=data, files=files)
            return success, result
        finally:
            files['file'][1].close()

    def get_user_info(self) -> Optional[Dict]:
        """获取当前用户信息"""
        success, result = self.get('/api/user/info', expect_json=True)
        if success:
            return result
        return None

    def capture_var(self, name: str, value: Any):
        """捕获变量"""
        self.captured_vars[name] = value
        logger.debug(f"Captured var: {name} = {value}")

    def get_captured_var(self, name: str) -> Any:
        """获取捕获的变量"""
        return self.captured_vars.get(name)

    def resolve_value(self, value: str) -> Any:
        """
        解析值（支持变量替换）

        例如: "${pending_ids[0]}" 会被解析为捕获的pending_ids列表的第一个元素
        """
        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            var_expr = value[2:-1]
            # 处理数组索引，如 pending_ids[0]
            if '[' in var_expr and var_expr.endswith(']'):
                var_name = var_expr.split('[')[0]
                index_str = var_expr.split('[')[1].rstrip(']')
                var_value = self.get_captured_var(var_name)
                if isinstance(var_value, list):
                    try:
                        index = int(index_str)
                        return var_value[index]
                    except (ValueError, IndexError):
                        return value
            return self.get_captured_var(var_expr)
        return value
