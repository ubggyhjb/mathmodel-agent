#!/usr/bin/env python3
import argparse,json,subprocess,sys
from pathlib import Path
import gate_common as gc
TOOLS=['pdftoppm','mgs','gswin64c','mutool','magick','inkscape']
VER_ARGS={'pdftoppm':['-v'],'mgs':['--version'],'gswin64c':['--version'],'mutool':['-v'],'magick':['-version'],'inkscape':['--version']}
def probe():
 for n in TOOLS:
  x=gc.detect_tool(n, VER_ARGS.get(n, ['--version']))
  if x.get('path'): return {'kind':n,'path':x['path'],'version':x.get('version')}
 return {'kind':None,'path':None,'version':None}
def main():
 gc.force_utf8();p=argparse.ArgumentParser();p.add_argument('--probe',action='store_true');p.add_argument('command',nargs='?',choices=['render']);p.add_argument('--pdf');p.add_argument('--out-dir');p.add_argument('--dpi',type=int,default=160);p.add_argument('--first',type=int,default=1);p.add_argument('--last',type=int);a=p.parse_args();tool=probe()
 if a.probe: print(json.dumps(tool,ensure_ascii=False));return 0 if tool['path'] else 1
 if a.command!='render' or not a.pdf or not a.out_dir: p.error('render requires --pdf and --out-dir')
 if not tool['path']: print('FAIL 未找到渲染工具',file=sys.stderr);return 1
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);last=a.last or 10**9
 try:
  if tool['kind']=='pdftoppm':cmd=[tool['path'],'-png','-r',str(a.dpi),'-f',str(a.first),'-l',str(last),a.pdf,str(out/'page')]
  elif tool['kind'] in ('mgs','gswin64c'):cmd=[tool['path'],'-dSAFER','-dBATCH','-dNOPAUSE','-sDEVICE=pngalpha',f'-r{a.dpi}',f'-dFirstPage={a.first}',f'-dLastPage={last}',f'-sOutputFile={out}/page-%03d.png',a.pdf]
  elif tool['kind']=='mutool':cmd=[tool['path'],'draw','-r',str(a.dpi),'-o',str(out/'page-%03d.png'),a.pdf,str(a.first),str(last)]
  else:cmd=[tool['path'],'-density',str(a.dpi),a.pdf,str(out/'page.png')]
  subprocess.run(cmd,check=True);return 0
 except Exception as e: print(f'FAIL 渲染失败: {e}',file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
