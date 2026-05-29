#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
wtfutil — 面向日常脚本与自动化场景的 Python 工具库。

推荐用法（按需导入，IDE 可自动补全）：
    from wtfutil import requests_session, read_text, send
    from wtfutil.httputil import ChunkedConfig
    from wtfutil.util import UniqueQueue, get_resource
"""

# ── 资源路径 ──────────────────────────────────────────────────────────────────
from ._base import (
    get_resource,
    get_resource_dir,
)

# ── 文件 ──────────────────────────────────────────────────────────────────────
from .fileutil import (
    file_md5,
    file_sha1,
    file_sha256,
    list_files,
    list_directories,
    touch,
    read_text,
    read_json,
    read_lines,
    write_text,
    write_lines,
    write_json,
    JarAnalyzer,
)

# ── HTTP ──────────────────────────────────────────────────────────────────────
from .httputil import (
    requests_session,
    RequestsSession,
    BaseUrlSession,
    EnhancedResponse,
    CustomSslContextHttpAdapter,
    ChunkedConfig,
    ChunkedAdapter,
    DESAdapter,
    httpraw,
    get_redirect_target,
    patch_redirect,
    remove_ssl_verify,
    patch_getproxies,
    is_private_ip,
    is_internal_url,
    is_wildcard_dns,
    is_wildcard_dns_batch,
    is_valid_ip,
    get_maindomain,
    url2ip,
    is_port_in_use,
    get_base_url,
    build_absolute_url,
)

# ── 字符串 / 加解密 ────────────────────────────────────────────────────────────
from .strutil import (
    tobytes,
    tostr,
    tobool,
    removesuffix,
    removeprefix,
    url_encode_all,
    unicode_digit_hex_escape,
    unicode_digit_hex_encode,
    url_decode,
    url_encode,
    qp_encode_all,
    uuencode,
    base64decode,
    base64encode,
    base64_urlencode,
    base64_urldecode,
    urlsafe_base64encode,
    urlsafe_base64decode,
    base64pickle,
    base64unpickle,
    rsa_encrypt,
    rsa_decrypt,
    des_encrypt,
    des_decrypt,
    str_md5,
    str_sha1,
    str_sha256,
    get_middle_text,
    splitlines,
    rand_base,
    rand_case,
    match1,
    string_to_bash_variable,
    normalize_spaces,
    extract_dict,
    format_bytes,
    align_text,
    utf8_overlong_encoding,
    utf7_encode,
    ghost_bits_byte,
    ghost_bits_encode,
    ghost_bits_decode_to_bytes,
    ghost_bits_decode,
)

# ── 数据库 ────────────────────────────────────────────────────────────────────
from .sqlutil import (
    Dict,
    Database,
    SQLite,
    MYSQL,
    ScriptRunner,
    next_id,
    join_field_value,
    join_field,
    join_value,
)

# ── 进程（Windows）────────────────────────────────────────────────────────────
from .procutil import (
    find_process_by_name,
    suspend_process,
    suspend_process_by_pid,
    resume_process,
    resume_process_by_pid,
    find_python_process_by_script,
    find_python_processes_by_script,
    find_python_process_details_by_script,
    kill_python_processes_by_script,
    find_python_processes_by_cmdline,
    find_python_process_details_by_cmdline,
    kill_python_processes_by_cmdline,
    list_all_python_process_details,
)

# ── 通知 ──────────────────────────────────────────────────────────────────────
from .notifyutil import (
    push_config,
    send,
    one,
    bark,
    console,
    dingding_bot,
    feishu_bot,
    feishu_text,
    feishu_richtext,
    go_cqhttp,
    gotify,
    iGot,
    serverJ,
    pushdeer,
    chat,
    pushplus_bot,
    qmsg_bot,
    wecom_app,
    WeCom,
    wecom_bot,
    telegram_bot,
    aibotk,
    smtp,
    pushme,
    pipehub,
    xtuis,
    aiops_phone,
    showdoc,
    notifyx,
    chronocat,
    custom_notify,
)

# ── 翻译 ──────────────────────────────────────────────────────────────────────
from .translateutil import (
    BaiduTranslateApi,
)

# ── 图片 ──────────────────────────────────────────────────────────────────────
from .imgutil import (
    img_config,
    ImageFetchError,
    fetch_random_bytes,
    random_avatar_bytes,
)

# ── 单实例 ────────────────────────────────────────────────────────────────────
from .singleinstance import (
    SingleInstance,
    SingleInstanceException,
    single_instance,
)

# ── 杂项工具 ──────────────────────────────────────────────────────────────────
from .util import (
    UniqueQueue,
    measure_time,
    unique_items,
    current_datetime,
    format_datetime,
    parse_datetime,
    cut_list,
    group_data,
)

__all__ = [
    # _base
    'get_resource', 'get_resource_dir',
    # fileutil
    'file_md5', 'file_sha1', 'file_sha256',
    'list_files', 'list_directories', 'touch',
    'read_text', 'read_json', 'read_lines',
    'write_text', 'write_lines', 'write_json',
    'JarAnalyzer',
    # httputil
    'requests_session', 'RequestsSession', 'BaseUrlSession',
    'EnhancedResponse', 'CustomSslContextHttpAdapter',
    'ChunkedConfig', 'ChunkedAdapter', 'DESAdapter',
    'httpraw',
    'get_redirect_target', 'patch_redirect', 'remove_ssl_verify', 'patch_getproxies',
    'is_private_ip', 'is_internal_url', 'is_wildcard_dns', 'is_wildcard_dns_batch',
    'is_valid_ip', 'get_maindomain', 'url2ip', 'is_port_in_use',
    'get_base_url', 'build_absolute_url',
    # strutil
    'tobytes', 'tostr', 'tobool',
    'removesuffix', 'removeprefix',
    'url_encode_all', 'unicode_digit_hex_escape', 'unicode_digit_hex_encode',
    'url_decode', 'url_encode', 'qp_encode_all', 'uuencode',
    'base64decode', 'base64encode', 'base64_urlencode', 'base64_urldecode',
    'urlsafe_base64encode', 'urlsafe_base64decode', 'base64pickle', 'base64unpickle',
    'rsa_encrypt', 'rsa_decrypt', 'des_encrypt', 'des_decrypt',
    'str_md5', 'str_sha1', 'str_sha256',
    'get_middle_text', 'splitlines', 'rand_base', 'rand_case',
    'match1', 'string_to_bash_variable', 'normalize_spaces',
    'extract_dict', 'format_bytes', 'align_text',
    'utf8_overlong_encoding', 'utf7_encode',
    'ghost_bits_byte', 'ghost_bits_encode', 'ghost_bits_decode_to_bytes', 'ghost_bits_decode',
    # sqlutil
    'Dict', 'Database', 'SQLite', 'MYSQL', 'ScriptRunner',
    'next_id', 'join_field_value', 'join_field', 'join_value',
    # procutil
    'find_process_by_name',
    'suspend_process', 'suspend_process_by_pid',
    'resume_process', 'resume_process_by_pid',
    'find_python_process_by_script', 'find_python_processes_by_script',
    'find_python_process_details_by_script', 'kill_python_processes_by_script',
    'find_python_processes_by_cmdline', 'find_python_process_details_by_cmdline',
    'kill_python_processes_by_cmdline', 'list_all_python_process_details',
    # notifyutil
    'push_config', 'send', 'one',
    'bark', 'console', 'dingding_bot',
    'feishu_bot', 'feishu_text', 'feishu_richtext',
    'go_cqhttp', 'gotify', 'iGot', 'serverJ',
    'pushdeer', 'chat', 'pushplus_bot', 'qmsg_bot',
    'wecom_app', 'WeCom', 'wecom_bot', 'telegram_bot',
    'aibotk', 'smtp', 'pushme', 'pipehub', 'xtuis',
    'aiops_phone', 'showdoc', 'notifyx', 'chronocat', 'custom_notify',
    # translateutil
    'BaiduTranslateApi',
    # imgutil
    'img_config', 'ImageFetchError', 'fetch_random_bytes', 'random_avatar_bytes',
    # singleinstance
    'SingleInstance', 'SingleInstanceException', 'single_instance',
    # util (misc)
    'UniqueQueue', 'measure_time', 'unique_items',
    'current_datetime', 'format_datetime', 'parse_datetime',
    'cut_list', 'group_data',
]
