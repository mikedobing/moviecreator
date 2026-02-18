from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

class ProgressTracker:
    def __init__(self, console):
        self.console = console

    def create_progress(self):
         return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=self.console
        )
