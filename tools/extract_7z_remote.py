"""Extract a dataset archive with the remote host's libarchive (no new dependency)."""
import argparse
import ctypes as C
import ctypes.util
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    lib=C.CDLL(C.util.find_library('archive'))
    for name,restype,argtypes in [('archive_read_new',C.c_void_p,[]),('archive_read_support_format_all',C.c_int,[C.c_void_p]),
        ('archive_read_support_filter_all',C.c_int,[C.c_void_p]),('archive_read_open_filename',C.c_int,[C.c_void_p,C.c_char_p,C.c_size_t]),
        ('archive_read_next_header',C.c_int,[C.c_void_p,C.POINTER(C.c_void_p)]),('archive_entry_pathname',C.c_char_p,[C.c_void_p]),
        ('archive_entry_filetype',C.c_uint,[C.c_void_p]),('archive_read_data',C.c_ssize_t,[C.c_void_p,C.c_void_p,C.c_size_t]),
        ('archive_error_string',C.c_char_p,[C.c_void_p]),('archive_read_free',C.c_int,[C.c_void_p])]:
        f=getattr(lib,name);f.restype=restype;f.argtypes=argtypes
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
    arc=lib.archive_read_new();lib.archive_read_support_format_all(arc);lib.archive_read_support_filter_all(arc)
    try:
        if lib.archive_read_open_filename(arc,str(args.archive).encode(),1<<20)!=0:raise RuntimeError(lib.archive_error_string(arc))
        entry=C.c_void_p();buffer=C.create_string_buffer(1<<20);count=0
        while True:
            status=lib.archive_read_next_header(arc,C.byref(entry))
            if status==1:break
            if status!=0:raise RuntimeError(lib.archive_error_string(arc))
            name=lib.archive_entry_pathname(entry).decode('utf-8');dest=(root/name).resolve()
            if not dest.is_relative_to(root):raise ValueError('Archive path escapes output')
            kind=lib.archive_entry_filetype(entry)
            if kind==0o040000:dest.mkdir(parents=True,exist_ok=True);continue
            if kind!=0o100000:raise ValueError('Nonregular archive member '+name)
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as stream:
                while True:
                    size=lib.archive_read_data(arc,buffer,len(buffer))
                    if size<0:raise RuntimeError(lib.archive_error_string(arc))
                    if size==0:break
                    stream.write(buffer.raw[:size])
            count+=1
        print('EXTRACTED',count,str(root),flush=True)
    finally:lib.archive_read_free(arc)


if __name__=='__main__':main()
