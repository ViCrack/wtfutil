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


def _calculate_file_hash(file_path: str | Path, algorithm: str) -> str:
    """分块读取文件并计算摘要，避免一次性把大文件读入内存。"""
    digest = hashlib.new(algorithm)
    with open(file_path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_md5(file_path: str | Path) -> str:
    """计算文件的 MD5 摘要。"""
    return _calculate_file_hash(file_path, "md5")


def file_sha1(file_path: str | Path) -> str:
    """计算文件的 SHA-1 摘要。"""
    return _calculate_file_hash(file_path, "sha1")


def file_sha256(file_path: str | Path) -> str:
    """计算文件的 SHA-256 摘要。"""
    return _calculate_file_hash(file_path, "sha256")


def list_files(directory: str | Path) -> list[str]:
    """列出目录中的直接子文件。"""
    directory_str = str(directory)
    return [
        os.path.join(directory_str, f)
        for f in os.listdir(directory_str)
        if os.path.isfile(os.path.join(directory_str, f))
    ]


def list_directories(directory: str | Path) -> list[str]:
    """列出目录中的直接子目录。"""
    directory_str = str(directory)
    return [
        os.path.join(directory_str, d)
        for d in os.listdir(directory_str)
        if os.path.isdir(os.path.join(directory_str, d))
    ]


def touch(filepath: str | Path, mode: int = 0o666, exist_ok: bool = True) -> None:
    Path(filepath).touch(mode=mode, exist_ok=exist_ok)


def read_text(
    filepath: Union[Path, str],
    mode: str = "r",
    encoding: str = "utf-8",
    not_exists_ok: bool = False,
    errors: str | None = None,
) -> str | bytes:
    """
    errors-->
    'ignore'：忽略无法解码的字符。直接跳过无法处理的字符，继续解码其他部分。
    'replace'：使用特定字符替代无法解码的字符，默认使用 '�' 代替。例如，b'\xe4\xb8\x96\xe7\x95\x8c'.decode('utf-8', errors='replace') 输出 '世界�'。
    'strict'：默认行为，如果遇到无法解码的字符，抛出 UnicodeDecodeError 异常。
    'backslashreplace'：使用 Unicode 转义序列替代无法解码的字符。例如，b'\xe4\xb8\x96\xe7\x95\x8c'.decode('ascii', errors='backslashreplace') 输出 '\\xe4\\xb8\\x96\\xe7\\x95\\x8c'。
    'xmlcharrefreplace'：使用 XML 实体替代无法解码的字符。例如，b'\xe4\xb8\x96\xe7\x95\x8c'.decode('ascii', errors='xmlcharrefreplace') 输出 '&#19990;&#30028;'。
    'surrogateescape'：将无法解码的字节转换为 Unicode 代理区转义码。例如，b'\\xe9'.decode('utf-8', errors='surrogateescape') 输出 '\\udce9'。
    """
    if not isinstance(mode, str) or "r" not in mode or any(flag in mode for flag in "wax+"):
        raise ValueError("read_text mode must be a read-only mode such as 'r' or 'rb'")
    if isinstance(filepath, Path):
        filepath = str(filepath)
    binary_mode = "b" in mode
    if binary_mode:
        encoding = None
        errors = None
    if not_exists_ok and not Path(filepath).is_file():
        return b"" if binary_mode else ""
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
    seen_lines: set[str] = set()
    with open(filepath, 'r', encoding=encoding) as f:
        # lines = f.readlines()
        # lines = [line.rstrip() for line in lines]  只会创建一个生成器 不会有性能问题
        for line in f:
            line = line.rstrip()
            if line:
                if unique and line in seen_lines:
                    # 去重
                    continue

                lines.append(line)
                if unique:
                    seen_lines.add(line)
    return lines


def write_text(filepath: Union[Path, str], content, mode='w', encoding='utf-8', newline=''):
    """
    写入文本内容到文件

    Args:
        filepath: 文件路径
        content: 要写入的内容
        mode: 文件打开模式，默认 'w'
        encoding: 文件编码，默认 'utf-8'
        newline: 换行符处理方式，默认 ''（不自动转换）
                - '': 不进行换行符转换（推荐，保持原始内容）
                - None: 启用平台相关的换行符转换（Windows: \n→\r\n）
                - '\n': 强制使用 LF（Unix/Linux 风格）
                - '\r\n': 强制使用 CRLF（Windows 风格）
                - '\r': 强制使用 CR（旧 Mac 风格）

    注意：
        - 默认 newline='' 不会自动转换换行符，保持内容原样
        - 如需平台相关的换行符转换，使用 newline=None
        - 二进制模式 ('wb') 下 newline 参数无效
    """
    if isinstance(filepath, Path):
        filepath = str(filepath)
    if 'b' in mode:
        encoding = None
        newline = None  # 二进制模式下 newline 无效
    if content is None:
        raise ValueError('content must not be None')
    with open(filepath, mode, encoding=encoding, newline=newline) as f:
        f.write(content)


def write_lines(filepath: Union[Path, str], lines, mode='w', encoding='utf-8', unique: bool = False, newline=''):
    """
    按行写入文本内容到文件

    Args:
        filepath: 文件路径
        lines: 要写入的行列表
        mode: 文件打开模式，默认 'w'
        encoding: 文件编码，默认 'utf-8'
        unique: 是否去重，默认 False
        newline: 换行符处理方式，默认 ''（不自动转换）
                - '': 不进行换行符转换（推荐，保持原始内容）
                - None: 启用平台相关的换行符转换（Windows: \n→\r\n）
                - '\n': 强制使用 LF（Unix/Linux 风格）
                - '\r\n': 强制使用 CRLF（Windows 风格）
                - '\r': 强制使用 CR（旧 Mac 风格）

    注意：
        - 默认 newline='' 不会自动转换换行符，每行末尾添加 '\n'
        - 如需平台相关的换行符转换，使用 newline=None
        - 函数会在每行末尾添加 '\n'，实际写入的换行符取决于 newline 参数
    """
    if isinstance(filepath, Path):
        filepath = str(filepath)
    if lines is None:
        raise ValueError('lines must not be None')
    if unique:
        # 去重并且保持原本顺序
        lines = list(dict.fromkeys(lines))

    with open(filepath, mode, encoding=encoding, newline=newline) as f:
        for line in lines:
            f.write(line + '\n')


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
    GUI_INDICATORS = [
        "java/awt/", "javax/swing/", "javafx/application/",
        "java.awt.", "javax.swing.", "javafx.application.",
    ]

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
        if not self.jar_path.is_file() or self.jar_path.suffix.lower() != ".jar":
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
                        raw_manifest_content = manifest.read().decode("utf-8")
                        # Manifest continuation lines begin with one space and belong to the previous field.
                        self._manifest_content = raw_manifest_content.replace("\r\n", "\n").replace("\n ", "")
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
                            self.jdk_version = self._java_release_from_major(major_version)
                            return
                    # 再检查标准路径
                    elif main_class_path in class_files:
                        with jar.open(main_class_path) as class_file:
                            class_file.read(4)  # 跳过魔数
                            _, major_version = struct.unpack(">HH", class_file.read(4))
                            self.jdk_version = self._java_release_from_major(major_version)
                            return

                # 检查第一个 .class 文件
                versions = set()
                for file in class_files[:5]:  # 限制检查前 5 个，避免性能问题
                    with jar.open(file) as class_file:
                        class_file.read(4)  # 跳过魔数
                        _, major_version = struct.unpack(">HH", class_file.read(4))
                        versions.add(self._java_release_from_major(major_version))
                    if len(versions) > 1:
                        self.jdk_version = max(versions)  # 使用最高版本
                        return
                self.jdk_version = versions.pop() if versions else 0
        except Exception:
            self.jdk_version = 0

    @classmethod
    def _java_release_from_major(cls, major_version: int) -> int:
        """将 class major 映射为 Java release，并兼容 Java 22 及后续版本。"""
        if major_version in cls.JAVA_VERSION_MAP:
            return cls.JAVA_VERSION_MAP[major_version]
        return major_version - 44 if major_version >= 45 else 0

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
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=temp_dir,
                    timeout=30,
                )
                stdout = output.stdout
                if any(indicator in stdout for indicator in self.GUI_INDICATORS):
                    self.recommended_executable = "javaw"
                # 额外检查是否有 CLI 相关标志
                elif "main([Ljava/lang/String;)V" in stdout and "java/io/Console" not in stdout:
                    self.recommended_executable = "java"
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
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
