from __future__ import annotations

from src.utils.ops_response import format_ops_response_body


def test_format_ops_response_body_pretty_prints_full_json_payload():
    body = """{"code":200,"message":"success","request_id":"43e2272098a04f34882ef1de86ad8ac5","supervisorctl":{"err":"/usr/lib/python3/dist-packages/supervisor/options.py:13: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.\\n  import pkg_resources","out":"error: <class 'PermissionError'>, [Errno 13] Permission denied: file: /usr/lib/python3/dist-packages/supervisor/xmlrpc.py line: 560","rc":1}}"""

    formatted = format_ops_response_body("/launch_stacker", body)

    assert (
        formatted
        == """{
  "code": 200,
  "message": "success",
  "request_id": "43e2272098a04f34882ef1de86ad8ac5",
  "supervisorctl": {
    "err": "/usr/lib/python3/dist-packages/supervisor/options.py:13: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.\\n  import pkg_resources",
    "out": "error: <class 'PermissionError'>, [Errno 13] Permission denied: file: /usr/lib/python3/dist-packages/supervisor/xmlrpc.py line: 560",
    "rc": 1
  }
}"""
    )


def test_format_ops_response_body_strips_ssh_motd():
    body = """Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 6.5.0-1023-aws x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

  System information as of Mon May 18 11:17:08 UTC 2026

  System load:  4.82861328125       Processes:             3895
  Usage of /:   92.0% of 968.99GB   Users logged in:       2
  Memory usage: 70%                 IPv4 address for ens5: 172.31.41.68
  Swap usage:   0%

  => / is using 92.0% of 968.99GB

173 updates can be applied immediately.
Run 'do-release-upgrade' to upgrade to it.

*** System restart required ***
✅ success
==================================================================
kucoincpp_ATWO_USDT_twkpi_st_1.txtpb.INFO:
NEW_ORDER_STATUS_ACCEPTED = 26"""

    formatted = format_ops_response_body("/get_stacker_accepted_orders", body)

    assert (
        formatted
        == """✅ success
==================================================================
kucoincpp_ATWO_USDT_twkpi_st_1.txtpb.INFO:
NEW_ORDER_STATUS_ACCEPTED = 26"""
    )
