"""One isolated idle-gated local advisory call; no tools or broker access."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import calendar_ollama as runner

def main():
    prompt=sys.stdin.read(50001)
    if not 1<=len(prompt)<=50000: raise ValueError('bounded prompt required')
    runner.TIMEOUT_SECONDS=110
    folder=ROOT/'runtime'/'backtest-lab-advisor'
    exe=Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Ollama/ollama.exe'
    schema={'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False}
    _,answer,_,_=runner.generate({},prompt,schema,exe,folder)
    value=json.loads(answer)
    print(json.dumps({'text':value['text'],'model':runner.MODEL},ensure_ascii=True))

if __name__=='__main__': main()
