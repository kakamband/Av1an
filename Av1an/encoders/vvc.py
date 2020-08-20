import subprocess
from distutils.spawn import find_executable
from pathlib import Path
from subprocess import PIPE, STDOUT

from Av1an.arg_parse import Args
from Av1an.chunk import Chunk
from Av1an.commandtypes import MPCommands, CommandPair, Command
from Av1an.encoders.encoder import Encoder
from Av1an.utils import list_index_of_regex


class Vvc(Encoder):

    def __init__(self):
        super(Vvc, self).__init__(
            encoder_bin='vvc_encoder',
            default_args=[],
            output_extension='h266'
        )

    def compose_1_pass(self, a: Args, c: Chunk, output) -> MPCommands:
        yuv_file: str = Vvc.get_yuv_file_path(c).as_posix()
        return [
            CommandPair(
                [],
                ['vvc_encoder', '-c', a.vvc_conf, '-i', yuv_file, *a.video_params, '-f', str(c.frames),
                 '--InputBitDepth=10', '--OutputBitDepth=10', '-b', output]
            )
        ]

    def compose_2_pass(self, a: Args, c: Chunk, output) -> MPCommands:
        raise ValueError('VVC does not support 2 pass encoding')


    def man_q(self, command: Command, q: int):
        """Return command with new cq value

        :param command: old command
        :param q: new cq value
        :return: command with new cq value"""

        adjusted_command = command.copy()


        i = list_index_of_regex(adjusted_command, r"-q")
        adjusted_command[i + 1] = f'{q}'

        return adjusted_command

    def make_pipes(self, a: Args, c: Chunk, passes, current_pass, output, man_q=None):
        """
        reates a pipe for the given chunk with the given args

        :param a: the Args
        :param c: the Chunk
        :param passes: the total number of passes (1 or 2)
        :param current_pass: the current_pass
        :param man_q: use a diffrent quality
        :return: a Pipe attached to the encoders stdout
        """

        filter_cmd, enc_cmd = self.compose_1_pass(a, c, output)[0] if passes == 1 else \
                              self.compose_2_pass(a, c, output)[current_pass - 1]

        if man_q:
            enc_cmd = self.man_q(enc_cmd, man_q)
        elif c.vmaf_target_cq:
            enc_cmd = self.man_q(enc_cmd, c.vmaf_target_cq)

        pipe = subprocess.Popen(enc_cmd, stdout=PIPE,
                                stderr=STDOUT,
                                universal_newlines=True)
        return pipe


    def check_exists(self) -> bool:
        # vvc also requires a special concat executable
        if find_executable('vvc_concat') is not None:
            print('vvc concatenation executable "vvc_concat" not found')
        return super().check_exists()

    @staticmethod
    def get_yuv_file_path(chunk: Chunk) -> Path:
        """
        Gets the yuv path to be used for a given chunk

        :param chunk: the Chunk
        :return: a yuv file path for the chunk
        """
        return (chunk.temp / 'split') / f'{chunk.name}.yuv'

    @staticmethod
    def to_yuv(chunk: Chunk) -> Path:
        """
        Generates a yuv file for a given chunk

        :param chunk: the Chunk
        :return: a yuv file path for the chunk
        """
        output = Vvc.get_yuv_file_path(chunk)

        ffmpeg_gen_pipe = subprocess.Popen(chunk.ffmpeg_gen_cmd, stdout=PIPE, stderr=STDOUT)

        # TODO: apply ffmpeg filter to the yuv file
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', '-', '-f', 'rawvideo', '-vf', 'format=yuv420p10le',
               output.as_posix()]
        pipe = subprocess.Popen(cmd, stdin=ffmpeg_gen_pipe.stdout, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
        pipe.wait()

        return output

