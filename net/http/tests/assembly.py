"""Assemble Monotonic's seven native implementations using the compiler probe.
This verifies code generation/ABI syntax, not execution on foreign hardware.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

probe, clang = (str(Path(p).resolve()) for p in sys.argv[1:])
stdlib = Path(__file__).resolve().parents[3]
source = (stdlib/'time/monotonic_native.oc').read_text()
blocks = dict(re.findall(r'asm (\w+/\w+) \{\n(.*?)\n    \}',source,re.S))
targets = {
    'x86_64/linux':'x86_64-linux-gnu',
    'aarch64/linux':'aarch64-linux-gnu',
    'riscv64/linux':'riscv64-linux-gnu',
    'x86_64/macos':'x86_64-apple-macosx11.0',
    'aarch64/macos':'arm64-apple-macosx11.0',
    'x86_64/windows':'x86_64-windows-gnu',
    'aarch64/windows':'aarch64-windows-gnu',
}
assert blocks.keys()==targets.keys()
with tempfile.TemporaryDirectory(prefix='ocean-clock-asm-') as tmp:
    root=Path(tmp)
    for selector,body in blocks.items():
        program=root/'probe.oc'
        program.write_text('package probe; func sample() { asm '+selector+' {\n'+body+'\n} }')
        result=subprocess.run([probe,str(program)],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,(selector,result.stderr)
        ir=root/'module.ll';ir.write_text(result.stdout)
        for optimization in ('-O0','-O2'):
            result=subprocess.run([clang,'--target='+targets[selector],optimization,'-Wno-override-module','-x','ir',str(ir),'-c','-o',str(root/'clock.o')],capture_output=True,text=True,timeout=30)
            assert result.returncode==0,(selector,optimization,result.stderr)
print('All seven monotonic-clock variants assembled at -O0 and -O2')
