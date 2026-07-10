"""
测试密码配置功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_get_default_password():
    """测试获取默认密码配置"""
    from app.utils import get_default_password
    
    try:
        password = get_default_password()
        print(f"✓ 成功获取默认密码: {password}")
        assert password == "P@ss301", f"默认密码不正确，期望 'P@ss301'，实际 '{password}'"
        print("✓ 默认密码验证通过")
        return True
    except Exception as e:
        print(f"✗ 获取默认密码失败: {e}")
        return False


def test_config_structure():
    """测试配置文件结构"""
    from app.utils import get_config
    
    try:
        config = get_config()
        
        # 检查system节点
        assert "system" in config, "配置中缺少 'system' 节点"
        print("✓ 配置包含 'system' 节点")
        
        # 检查default_password
        assert "default_password" in config["system"], "配置中缺少 'system.default_password'"
        print("✓ 配置包含 'system.default_password'")
        
        # 检查值
        password = config["system"]["default_password"]
        assert password, "default_password 不能为空"
        print(f"✓ default_password 值: {password}")
        
        return True
    except Exception as e:
        print(f"✗ 配置结构测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_password_hash():
    """测试密码哈希功能"""
    from werkzeug.security import generate_password_hash, check_password_hash
    from app.utils import get_default_password
    
    try:
        password = get_default_password()
        
        # 生成哈希
        hash_value = generate_password_hash(password)
        print(f"✓ 成功生成密码哈希")
        
        # 验证哈希
        assert check_password_hash(hash_value, password), "密码哈希验证失败"
        print("✓ 密码哈希验证通过")
        
        # 验证错误密码
        assert not check_password_hash(hash_value, "wrong_password"), "错误密码不应该通过验证"
        print("✓ 错误密码正确拒绝")
        
        return True
    except Exception as e:
        print(f"✗ 密码哈希测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("密码配置功能测试")
    print("=" * 60)
    print()
    
    tests = [
        ("配置文件结构测试", test_config_structure),
        ("获取默认密码测试", test_get_default_password),
        ("密码哈希功能测试", test_password_hash),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n[测试] {name}")
        print("-" * 60)
        result = test_func()
        results.append((name, result))
        print()
    
    # 输出总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")
    
    print()
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n✓ 所有测试通过！")
        return 0
    else:
        print(f"\n✗ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
