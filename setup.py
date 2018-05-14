#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
import sys
import os.path
curdir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(curdir, 'infra'))

import infra
from infra.packages import LLVM
from infra.util import run, qjoin


class LibcallCount(infra.Instance):
    name = 'libcallcount'

    def __init__(self, llvm_version):
        self.llvm = infra.packages.LLVM(version=llvm_version,
                                        compiler_rt=False,
                                        patches=['gold-plugins', 'statsfilter'])
        self.passes = infra.packages.LLVMPasses(
                self.llvm, os.path.join(curdir, 'llvm-passes'),
                'skeleton', use_builtins=True)
        self.runtime = LibcallCounterRuntime()

    def dependencies(self):
        yield self.llvm
        yield self.passes
        yield self.runtime

    def configure(self, ctx):
        self.llvm.configure(ctx)
        self.passes.configure(ctx)
        self.runtime.configure(ctx)
        LLVM.add_plugin_flags(ctx, '-count-libcalls', '-dump-ir')

    def prepare_run(self, ctx):
        prevlibpath = os.getenv('LD_LIBRARY_PATH', '').split(':')
        libpath = self.runtime.path(ctx)
        ctx.runenv.setdefault('LD_LIBRARY_PATH', prevlibpath).insert(0, libpath)


class LibcallCounterRuntime(infra.Package):
    def ident(self):
        return 'libcallcount-runtime'

    def fetch(self, ctx):
        pass

    def build(self, ctx):
        os.chdir(os.path.join(ctx.paths.root, 'runtime'))
        run(ctx, [
            'make', '-j%d' % ctx.jobs,
            'OBJDIR=' + self.path(ctx)
        ])

    def install(self, ctx):
        pass

    def is_fetched(self, ctx):
        return True

    def is_built(self, ctx):
        return os.path.exists('libcount.so')

    def is_installed(self, ctx):
        return self.is_built(ctx)

    def configure(self, ctx):
        ctx.ldflags += ['-L' + self.path(ctx), '-lcount']


class HelloWorld(infra.Target):
    name = 'hello-world'

    def is_fetched(self, ctx):
        return True

    def fetch(self, ctx):
        pass

    def build(self, ctx, instance):
        os.chdir(os.path.join(ctx.paths.root, self.name))
        run(ctx, [
            'make', '--always-make',
            'OBJDIR=' + self.path(ctx, instance.name),
            'CC=' + ctx.cxx,
            'CFLAGS=' + qjoin(ctx.cflags),
            'LDFLAGS=' + qjoin(ctx.ldflags)
        ])

    def link(self, ctx, instance):
        pass

    def binary_paths(self, ctx, instance):
        return [self.path(ctx, instance.name, 'hello')]

    def run(self, ctx, instance):
        os.chdir(self.path(ctx, instance.name))
        run(ctx, './hello', teeout=True, allow_error=True)


if __name__ == '__main__':
    setup = infra.Setup(__file__)

    # TODO: more recent LLVM
    instance = LibcallCount('3.8.0')
    setup.add_instance(infra.instances.ClangLTO(instance.llvm))
    setup.add_instance(instance)

    setup.add_target(HelloWorld())
    setup.add_target(infra.targets.SPEC2006(
        source='git@bitbucket.org:vusec/spec-cpu2006-cd.git',
        source_type='git',
    ))

    setup.main()