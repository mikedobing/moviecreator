
import sys
import traceback
from click.testing import CliRunner

try:
    from main import cli
except Exception:
    print("Error importing main:")
    traceback.print_exc()
    sys.exit(1)

print("Starting debug run...")

runner = CliRunner()
try:
    # prompt_input=None to prevent hanging on input
    result = runner.invoke(cli, ['phase3', '--novel-id', 'c86f2802-10a3-4e02-9548-cece751a2fdb', '--api', 'seedance'], catch_exceptions=False)
    print("Result Output:")
    print(result.output)
    if result.exception:
        print("Result Exception:")
        print(result.exception)
except Exception:
    with open("debug_error.log", "w") as f:
        f.write("Caught exception during invoke:\n")
        traceback.print_exc(file=f)
    print("Exception written into debug_error.log")
