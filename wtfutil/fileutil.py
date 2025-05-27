import hashlib
import json
import os
import struct
import subprocess
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from typing import Union


def file_md5(file_path) -> str:
    md5lib = hashlib.md5()
    with open(file_path, 'rb') as f:
        md5lib.update(f.read())
    return md5lib.hexdigest()


def file_sha1(file_path):
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as f:
        sha1.update(f.read())
    return sha1.hexdigest()


def file_sha256(file_path):
    sha1 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        sha1.update(f.read())
    return sha1.hexdigest()


def list_files(directory):
    """List all files in a directory."""
    return [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]


def list_directories(directory):
    """List all directories in a directory."""
    return [os.path.join(directory, d) for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]


def touch(filepath, mode=0o666, exist_ok=True):
    return Path(filepath, mode=mode, exist_ok=exist_ok).touch()


def read_text(filepath: Union[Path, str], mode='r', encoding='utf-8', not_exists_ok: bool = False, errors=None) -> str:
    """
    errors-->
    'ignore'：忽略无法解码的字符。直接跳过无法处理的字符，继续解码其他部分。
    'replace'：使用特定字符替代无法解码的字符，默认使用 '�' 代替。例如，b'\xe4\xb8\x96\xe7\x95\x8c'.decode('utf-8', errors='replace') 输出 '世界�'。
    'strict'：默认行为，如果遇到无法解码的字符，抛出 UnicodeDecodeError 异常。
    'backslashreplace'：使用 Unicode 转义序列替代无法解码的字符。例如，b'\xe4\xb8\x96\xe7\x95\x8c'.decode('ascii', errors='backslashreplace') 输出 '\\xe4\\xb8\\x96\\xe7\\x95\\x8c'。
    'xmlcharrefreplace'：使用 XML 实体替代无法解码的字符。例如，b'\xe4\xb8\x96\xe7\x95\x8c'.decode('ascii', errors='xmlcharrefreplace') 输出 '&#19990;&#30028;'。
    'surrogateescape'：将无法解码的字节转换为 Unicode 符号 '�' 的转义码。例如，当解码 Latin-1 字符串时，b'\xe9'.decode('latin-1', errors='surrogateescape') 输出 '\udce9'。
    """
    if isinstance(filepath, Path):
        filepath = str(filepath)
    if mode == 'rb':
        encoding = None
    if not_exists_ok and not Path(filepath).is_file():
        return ''
    with open(filepath, mode, encoding=encoding, errors=errors) as f:
        content = f.read()
    return content


def read_json(filepath: Union[Path, str], encoding='utf-8', not_exists_ok: bool = False) -> dict:
    if isinstance(filepath, Path):
        filepath = str(filepath)
    if not_exists_ok and not Path(filepath).is_file():
        return {}
    with open(filepath, 'r', encoding=encoding) as f:
        return json.load(f)


def read_lines(filepath: Union[Path, str], encoding='utf-8', not_exists_ok: bool = False, unique: bool = False) -> list:
    if isinstance(filepath, Path):
        filepath = str(filepath)
    lines = []
    if not_exists_ok and not Path(filepath).is_file():
        return lines
    with open(filepath, 'r', encoding=encoding) as f:
        # lines = f.readlines()
        # lines = [line.rstrip() for line in lines]  只会创建一个生成器 不会有性能问题
        for line in f:
            line = line.rstrip()
            if line:
                if unique and line in lines:
                    # 去重
                    continue

                lines.append(line)
    return lines


def write_text(filepath: Union[Path, str], content, mode='w', encoding='utf-8'):
    if isinstance(filepath, Path):
        filepath = str(filepath)
    if mode == 'wb':
        encoding = None
    if content is None:
        raise ValueError('content must not be None')
    with open(filepath, mode, encoding=encoding) as f:
        f.write(content)


def write_lines(filepath: Union[Path, str], lines, mode='w', encoding='utf-8', unique: bool = False):
    if isinstance(filepath, Path):
        filepath = str(filepath)
    if lines is None:
        raise ValueError('lines must not be None')
    if unique:
        # 去重并且保持原本顺序
        lines = list(dict.fromkeys(lines))

    with open(filepath, mode, encoding=encoding) as f:
        for l in lines:
            f.write(l + '\n')


def write_json(filepath: Union[Path, str], json_obj: dict, encoding='utf-8'):
    if isinstance(filepath, Path):
        filepath = str(filepath)
    if json_obj is None:
        raise ValueError('json_obj must not be None')
    with open(filepath, 'w', encoding=encoding) as f:
        json.dump(json_obj, f, indent=4, ensure_ascii=False)


class JarAnalyzer:
    # JDK 版本映射表，仅用于映射数字版本
    JAVA_VERSION_MAP = {
        45: 1, 46: 2, 47: 3, 48: 4, 49: 5,
        50: 6, 51: 7, 52: 8, 53: 9, 54: 10,
        55: 11, 56: 12, 57: 13, 58: 14, 59: 15,
        60: 16, 61: 17, 62: 18, 63: 19, 64: 20,
        65: 21
    }

    SPRING_BOOT_INDICATORS = ["org.springframework.", "Spring-Boot", "BOOT-INF/"]
    GUI_INDICATORS = ["java/awt/", "javax/swing/", "javafx/application/"]

    def __init__(self, jar_path: str):
        self.jar_path = Path(jar_path).resolve()
        self.jar_file = self.jar_path.name
        self.jdk_version = 0  # 默认值为 0，表示未知
        self.is_spring_boot = False
        self.recommended_executable = "java"
        self.main_class = None  # 新增：保存 Main-Class
        self._manifest_content = None
        self._is_executable_jar = False  # 新增：是否是可执行 JAR

        # 检查文件是否存在，不存在则抛出异常
        if not self.jar_path.exists():
            raise FileNotFoundError(f"JAR 文件不存在: {self.jar_path}")
        if not self.jar_path.is_file() or not self.jar_path.suffix == ".jar":
            raise ValueError(f"路径不是有效的 JAR 文件: {self.jar_path}")

        # 初始化时直接进行分析
        self._get_java_version()
        self._check_spring_boot()
        self._check_gui_application()

    def _read_manifest(self) -> None:
        """读取并缓存 META-INF/MANIFEST.MF 的内容，检查是否是可执行 JAR"""
        if self._manifest_content is None:
            try:
                with zipfile.ZipFile(self.jar_path, 'r') as jar:
                    with jar.open("META-INF/MANIFEST.MF") as manifest:
                        self._manifest_content = manifest.read().decode("utf-8")
                        # 检查是否有 Main-Class 或 Start-Class（Spring Boot）
                        lines = self._manifest_content.splitlines()
                        for line in lines:
                            if line.startswith("Main-Class:") or line.startswith("Start-Class:"):
                                self._is_executable_jar = True
                                break
            except Exception:
                self._manifest_content = ""
                self._is_executable_jar = False

    def _get_main_class(self) -> Optional[str]:
        """获取 JAR 文件中的 Main-Class，支持 Spring Boot 的 Start-Class"""
        self._read_manifest()
        if self._manifest_content:
            lines = self._manifest_content.splitlines()
            # 优先检查 Spring Boot 的 Start-Class
            for line in lines:
                if line.startswith("Start-Class:"):  # Spring Boot 的实际启动类
                    self.main_class = line.split(":", 1)[1].strip()
                    return self.main_class
            # 再检查标准的 Main-Class
            for line in lines:
                if line.startswith("Main-Class:"):
                    self.main_class = line.split(":", 1)[1].strip()
                    return self.main_class
        return None

    def _get_java_version(self) -> None:
        """解析 JAR 文件中的 .class 文件，获取 JDK 版本，优先使用 Main-Class，并检查版本一致性"""
        try:
            with zipfile.ZipFile(self.jar_path, 'r') as jar:
                class_files = [f for f in jar.namelist() if f.endswith(".class")]
                if not class_files:
                    self.jdk_version = 0
                    return

                # 优先检查 Main-Class
                main_class = self._get_main_class()
                if main_class:
                    main_class_path = main_class.replace('.', '/') + ".class"
                    # Spring Boot 的路径
                    spring_boot_main_class_path = f"BOOT-INF/classes/{main_class_path}"

                    # 先检查 Spring Boot 路径
                    if spring_boot_main_class_path in class_files:
                        with jar.open(spring_boot_main_class_path) as class_file:
                            class_file.read(4)  # 跳过魔数
                            _, major_version = struct.unpack(">HH", class_file.read(4))
                            self.jdk_version = self.JAVA_VERSION_MAP.get(major_version, 0)
                            return
                    # 再检查标准路径
                    elif main_class_path in class_files:
                        with jar.open(main_class_path) as class_file:
                            class_file.read(4)  # 跳过魔数
                            _, major_version = struct.unpack(">HH", class_file.read(4))
                            self.jdk_version = self.JAVA_VERSION_MAP.get(major_version, 0)
                            return

                # 检查第一个 .class 文件
                versions = set()
                for file in class_files[:5]:  # 限制检查前 5 个，避免性能问题
                    with jar.open(file) as class_file:
                        class_file.read(4)  # 跳过魔数
                        _, major_version = struct.unpack(">HH", class_file.read(4))
                        versions.add(self.JAVA_VERSION_MAP.get(major_version, 0))
                    if len(versions) > 1:
                        self.jdk_version = max(versions)  # 使用最高版本
                        return
                self.jdk_version = versions.pop() if versions else 0
        except Exception:
            self.jdk_version = 0

    def _check_spring_boot(self) -> None:
        """增强 Spring Boot 判断，结合 MANIFEST.MF 和文件结构"""
        self._read_manifest()
        if self._manifest_content:
            # 检查 MANIFEST.MF 中的 Spring Boot 标志
            self.is_spring_boot = any(
                indicator in self._manifest_content
                for indicator in self.SPRING_BOOT_INDICATORS
            )
        if not self.is_spring_boot:
            # 检查文件结构中是否有 BOOT-INF/ 目录
            try:
                with zipfile.ZipFile(self.jar_path, 'r') as jar:
                    self.is_spring_boot = any(
                        f.startswith("BOOT-INF/") for f in jar.namelist()
                    )
            except Exception:
                pass

    def _check_gui_application(self) -> None:
        """增强 GUI 判断，检查依赖和 Main-Class"""
        if self.is_spring_boot:
            return

        main_class = self._get_main_class()
        if not main_class:
            return

        try:
            with TemporaryDirectory() as temp_dir:
                output = subprocess.run(
                    ["javap", "-classpath", str(self.jar_path), "-s", main_class],
                    capture_output=True, text=True, check=True, cwd=temp_dir
                )
                stdout = output.stdout
                if any(indicator in stdout for indicator in self.GUI_INDICATORS):
                    self.recommended_executable = "javaw"
                # 额外检查是否有 CLI 相关标志
                elif "main([Ljava/lang/String;)V" in stdout and "java/io/Console" not in stdout:
                    self.recommended_executable = "java"
        except subprocess.CalledProcessError:
            # 如果 javap 失败，尝试检查 JAR 中的依赖
            try:
                with zipfile.ZipFile(self.jar_path, 'r') as jar:
                    for file in jar.namelist():
                        if file.endswith(".class"):
                            with jar.open(file) as class_file:
                                content = class_file.read().decode("utf-8", errors="ignore")
                                if any(indicator in content for indicator in self.GUI_INDICATORS):
                                    self.recommended_executable = "javaw"
                                    return
            except Exception:
                pass


__all__ = [
    'file_md5',
    'file_sha1',
    'file_sha256',
    'list_files',
    'list_directories',
    'touch',
    'read_text',
    'read_json',
    'read_lines',
    'write_text',
    'write_lines',
    'write_json',
    'JarAnalyzer'
]
