from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64


def encrypt_string(plaintext, password):
    """
    使用AES-256-GCM加密一个字符串。
    返回一个经过Base64编码的字符串，包含了盐、初始向量、密文和认证标签。
    """
    # 生成随机盐（Salt）和初始向量（IV）
    salt = os.urandom(16)
    iv = os.urandom(12)  # GCM推荐使用12字节的IV

    # 从密码派生密钥（Key Derivation）
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # AES-256密钥长度是32字节
        salt=salt,
        iterations=390000,  # 迭代次数，增加暴力破解难度
        backend=default_backend()
    )
    key = kdf.derive(password.encode())

    # 创建加密器并加密数据
    encryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv),
        backend=default_backend()
    ).encryptor()

    # 对明文进行加密（GCM模式不需要手动填充）
    ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()

    # 获取认证标签（GCM模式的特点）
    tag = encryptor.tag

    # 将盐、IV、密文和标签组合在一起，并用Base64编码以便存储或传输
    encrypted_data = salt + iv + tag + ciphertext
    return base64.b64encode(encrypted_data).decode('utf-8')


def decrypt_string(encrypted_data_b64, password):
    """
    解密一个由encrypt_string函数加密的Base64字符串。
    """
    # Base64解码
    encrypted_data = base64.b64decode(encrypted_data_b64)

    # 从解码的数据中分离出各个部分
    salt = encrypted_data[0:16]
    iv = encrypted_data[16:28]  # 接下来12字节是IV
    tag = encrypted_data[28:44]  # 接下来16字节是GCM标签
    ciphertext = encrypted_data[44:]  # 剩下的是密文

    # 从密码和盐派生密钥（必须使用相同的盐和参数）
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
        backend=default_backend()
    )
    key = kdf.derive(password.encode())

    # 创建解密器
    decryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv, tag),  # 传入IV和认证标签
        backend=default_backend()
    ).decryptor()

    # 解密数据
    decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()

    return decrypted_data.decode('utf-8')


# 使用示例
if __name__ == "__main__":
    original_string = "你好，这是一个测试字符串。"
    password = "qq"

    # 加密
    encrypted_b64 = encrypt_string(original_string, password)
    print(f"加密后的Base64字符串: {encrypted_b64}")

    # 解密
    try:
        decrypted_string = decrypt_string(encrypted_b64, password)
        print(f"解密后的字符串: {decrypted_string}")
    except Exception as e:
        print(f"解密失败！可能密码错误或数据被篡改。错误信息: {e}")