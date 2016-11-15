import py
import commands
import docutils.core
from docutils.parsers.rst import Directive, directives
from traceback import format_exc, print_exc
from sphinx.directives.code import CodeBlock
import pygal
from charter import Charter

class BenchmarkDirective(Directive):
    required_arguments = 1
    final_argument_whitespace = True
    has_content = True
    option_spec = {
        'timeline': directives.flag,
        'filter': directives.unchanged,
        'series': directives.unchanged,
        'group': directives.unchanged,
    }

    @classmethod
    def setup(cls):
        if cls.charter is not None:
            return
        root = py.path.local(__file__).dirpath('..', '..')
        revision = commands.getoutput('git rev-parse HEAD')
        benchdir = root.join('.benchmarks')
        cls.charter = Charter(benchdir, revision)
    charter = None

    def run(self):
        self.setup()
        try:
            return self._run()
        except Exception:
            ## import pdb;pdb.xpm()
            raise
            ## return [docutils.nodes.system_message(
            ##     'An exception as occured during graph generation:'
            ##     ' \n %s' % format_exc(), type='ERROR', source='/',
            ##     level=3)]

    def get_function(self, name):
        src = 'lambda b: ' + self.options[name]
        return eval(src, self.namespace)

    def _run(self):
        title = self.arguments[0]
        charts = self.charter.run_directive(title, self.options, self.content)
        nodes = []
        for chart in charts:
            svg = '<embed src="%s" />' % chart.render_data_uri()
            nodes.append(docutils.nodes.raw('', svg, format='html'))
        return nodes

def setup(app):
    app.add_directive('benchmark', BenchmarkDirective)
    return {'version': '0.1'}
