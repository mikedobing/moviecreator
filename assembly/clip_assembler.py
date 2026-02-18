import ffmpeg
from typing import List, Optional
from pydantic import BaseModel
import os

class AssemblyResult(BaseModel):
    success: bool
    output_path: str | None
    clip_count: int
    total_duration_seconds: float | None
    ffmpeg_command: str | None
    error: str | None

class ClipAssembler:
    def __init__(self, ffmpeg_path: str = 'ffmpeg'):
        self.ffmpeg_path = ffmpeg_path

    def assemble_scene(
        self,
        scene_id: str,
        clip_paths: List[str],
        output_path: str,
        transition_type: str = 'cut'
    ) -> AssemblyResult:
        try:
            # Create a temporary file list for concat demuxer
            list_path = f"{output_path}_list.txt"
            with open(list_path, 'w') as f:
                for path in clip_paths:
                    # FFmpeg requires absolute paths and specific escaping
                    abs_path = os.path.abspath(path).replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
            
            # Simple concat for now
            (
                ffmpeg
                .input(list_path, format='concat', safe=0)
                .output(output_path, c='copy')
                .overwrite_output()
                .run(cmd=self.ffmpeg_path, capture_stdout=True, capture_stderr=True)
            )
            
            # clean up list file
            os.remove(list_path)

            return AssemblyResult(
                success=True,
                output_path=output_path,
                clip_count=len(clip_paths),
                total_duration_seconds=0, # TODO: Calculate duration
                ffmpeg_command="ffmpeg concat",
                error=None
            )

        except ffmpeg.Error as e:
            return AssemblyResult(
                success=False,
                output_path=None,
                clip_count=len(clip_paths),
                total_duration_seconds=None,
                ffmpeg_command="ffmpeg concat",
                error=e.stderr.decode('utf8')
            )
        except Exception as e:
            return AssemblyResult(
                 success=False,
                output_path=None,
                clip_count=len(clip_paths),
                total_duration_seconds=None,
                ffmpeg_command="ffmpeg concat",
                error=str(e)
            )
