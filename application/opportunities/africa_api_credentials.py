"""Windows Credential Manager storage for one local Africa API research key."""
import ctypes
from ctypes import wintypes
import os

TARGET='JSETrading/AfricaAPI/Research'
_CRED_TYPE_GENERIC=1
_CRED_PERSIST_LOCAL_MACHINE=2
_NOT_FOUND=1168


class Credential(ctypes.Structure):
    _fields_=[('Flags',wintypes.DWORD),('Type',wintypes.DWORD),('TargetName',wintypes.LPWSTR),
              ('Comment',wintypes.LPWSTR),('LastWritten',wintypes.FILETIME),
              ('CredentialBlobSize',wintypes.DWORD),('CredentialBlob',ctypes.POINTER(ctypes.c_ubyte)),
              ('Persist',wintypes.DWORD),('AttributeCount',wintypes.DWORD),('Attributes',ctypes.c_void_p),
              ('TargetAlias',wintypes.LPWSTR),('UserName',wintypes.LPWSTR)]


def _library():
    if os.name != 'nt': raise OSError('Windows Credential Manager required')
    api=ctypes.WinDLL('advapi32',use_last_error=True)
    api.CredWriteW.argtypes=[ctypes.POINTER(Credential),wintypes.DWORD]; api.CredWriteW.restype=wintypes.BOOL
    api.CredReadW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype=wintypes.BOOL
    api.CredFree.argtypes=[ctypes.c_void_p]; api.CredFree.restype=None
    return api


def save_key(key, *, target=TARGET):
    if not isinstance(key,str) or not 8 <= len(key) <= 1024 or any(ch.isspace() for ch in key):
        raise ValueError('nonempty API key without whitespace required')
    encoded=key.encode('utf-8'); blob=(ctypes.c_ubyte*len(encoded)).from_buffer_copy(encoded)
    credential=Credential(); credential.Type=_CRED_TYPE_GENERIC; credential.TargetName=target
    credential.CredentialBlobSize=len(encoded); credential.CredentialBlob=ctypes.cast(blob,ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist=_CRED_PERSIST_LOCAL_MACHINE; credential.UserName='local-research'
    try:
        if not _library().CredWriteW(ctypes.byref(credential),0): raise ctypes.WinError(ctypes.get_last_error())
    finally:
        ctypes.memset(ctypes.addressof(blob),0,len(encoded))


def load_key(*, target=TARGET):
    api=_library(); ptr=ctypes.POINTER(Credential)()
    if not api.CredReadW(target,_CRED_TYPE_GENERIC,0,ctypes.byref(ptr)):
        error=ctypes.get_last_error()
        if error == _NOT_FOUND: return None
        raise ctypes.WinError(error)
    try:
        item=ptr.contents
        if not 8 <= item.CredentialBlobSize <= 4096: raise ValueError('invalid stored credential')
        return ctypes.string_at(item.CredentialBlob,item.CredentialBlobSize).decode('utf-8')
    finally:
        api.CredFree(ptr)
