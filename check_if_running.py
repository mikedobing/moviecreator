"""Check if the extraction process is actually running or stuck."""
import psutil
import time

# Find the python process running main.py
print("Looking for running extraction process...")

found = False
for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent']):
    try:
        cmdline = proc.info['cmdline']
        if cmdline and 'main.py' in ' '.join(cmdline) and 'run-all' in ' '.join(cmdline):
            found = True
            pid = proc.info['pid']
            name = proc.info['name']
            
            print(f"\n✓ Found process: PID {pid}")
            print(f"  Command: {' '.join(cmdline[-3:])}")
            
            # Check CPU usage over 3 seconds
            print(f"\n  Checking if process is active...")
            cpu_before = proc.cpu_percent(interval=1)
            time.sleep(2)
            cpu_after = proc.cpu_percent(interval=1)
            
            avg_cpu = (cpu_before + cpu_after) / 2
            
            if avg_cpu > 0.5:
                print(f"  ✓ Process is ACTIVE (CPU: {avg_cpu:.1f}%)")
                print(f"  The extraction is still running normally.")
            else:
                print(f"  ⚠️  Process has LOW activity (CPU: {avg_cpu:.1f}%)")
                print(f"  This might mean it's waiting for API response or potentially stuck.")
                
            # Check memory
            mem = proc.memory_info().rss / 1024 / 1024  # MB
            print(f"  Memory usage: {mem:.1f} MB")
            
            break
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue

if not found:
    print("\n❌ No running extraction process found")
    print("   The process may have completed or crashed")
