# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging
import os

from pylsp import hookimpl
from pylsp.lsp import SymbolKind

log = logging.getLogger(__name__)


@hookimpl
def pylsp_document_symbols(config, document):
    symbols_settings = config.plugin_settings('jedi_symbols')
    add_import_symbols = symbols_settings.get('include_import_symbols', True)

    symbols = []
    definitions = document.jedi_names(all_scopes=False)
    all_definitions = document.jedi_names(all_scopes=True)

    for definition in definitions:
        symbol = _extract_symbols(
            definition,
            all_definitions,
            include_vars=True,
            add_import_symbols=add_import_symbols,
        )
        if symbol is not None:
            symbols.append(symbol)

    return symbols


def _extract_symbols(name, all_names, include_vars, add_import_symbols):
    kind = None
    children = []
    signature = None

    if not _include_def(name):
        return None
    if name.type == 'statement' and not include_vars:
        return None

    if name._name.is_import():
        if not add_import_symbols:
            return None
    else:
        # For classes, we want to include all the methods and class constants
        if name.type == 'class':
            children.extend(
                child_symbol
                for child_symbol in (_extract_symbols(n,
                                                      all_names,
                                                      include_vars=True,
                                                      add_import_symbols=add_import_symbols)
                                     for n in name.defined_names())
                if child_symbol)

        if name.type == 'function':
            # Add the parameters as "detailed information"
            signatures = name.get_signatures()
            if signatures:
                params = signatures[0].params[:]
                if params and params[0].name == 'self':
                    params.pop(0)
                params = ', '.join(p.name for p in params)
                signature = f'({params})'

            # Mark the functions as a method if it's defined within a class
            if name.parent().type == 'class':
                kind = 'method'

            if name.parent().type == 'class' and name.name == '__init__':
                children.extend(_extract_fields(name, all_names))

            # Nested functions and classes are very much possible
            children.extend(
                child_symbol
                for child_symbol in (_extract_symbols(n,
                                                      all_names,
                                                      include_vars=False,
                                                      add_import_symbols=add_import_symbols)
                                     for n in name.defined_names())
                if child_symbol)

    symbol = {
        'name': name.name,
        'detail': signature,
        'range': _range(name),
        'selectionRange': _range(name),
        'kind': _kind(name) if kind is None else _SYMBOL_KIND_MAP[kind],
        'children': children,
    }
    return symbol


def _extract_fields(name, all_names):
    assert name.name == '__init__'
    symbols = []

    for candidate in all_names:
        if not candidate.full_name or not candidate.full_name.startswith(name.full_name + '.'):
            continue
        symbol = {
            'name': candidate.full_name.rpartition('.')[2],
            'range': _range(candidate),
            'selectionRange': _range(candidate),
            'kind': SymbolKind.Field,
        }
        symbols.append(symbol)
    return symbols


def _include_def(definition):
    return (
        # Don't tend to include parameters as symbols
        definition.type != 'param' and
        # Unused vars should also be skipped
        definition.name != '_' and
        _kind(definition) is not None
    )


def _range(definition):
    # This gets us more accurate end position
    definition = definition._name.tree_name.get_definition()
    (start_line, start_column) = definition.start_pos
    (end_line, end_column) = definition.end_pos
    return {
        'start': {'line': start_line - 1, 'character': start_column},
        'end': {'line': end_line - 1, 'character': end_column}
    }


def _tuple_range(definition):
    definition = definition._name.tree_name.get_definition()
    return (definition.start_pos, definition.end_pos)


_SYMBOL_KIND_MAP = {
    'none': SymbolKind.Variable,
    'type': SymbolKind.Class,
    'tuple': SymbolKind.Class,
    'dict': SymbolKind.Class,
    'dictionary': SymbolKind.Class,
    'function': SymbolKind.Function,
    'lambda': SymbolKind.Function,
    'generator': SymbolKind.Function,
    'class': SymbolKind.Class,
    'instance': SymbolKind.Class,
    'method': SymbolKind.Method,
    'builtin': SymbolKind.Class,
    'builtinfunction': SymbolKind.Function,
    'module': SymbolKind.Module,
    'file': SymbolKind.File,
    'xrange': SymbolKind.Array,
    'slice': SymbolKind.Class,
    'traceback': SymbolKind.Class,
    'frame': SymbolKind.Class,
    'buffer': SymbolKind.Array,
    'dictproxy': SymbolKind.Class,
    'funcdef': SymbolKind.Function,
    'property': SymbolKind.Property,
    'import': SymbolKind.Module,
    'keyword': SymbolKind.Variable,
    'constant': SymbolKind.Constant,
    'variable': SymbolKind.Variable,
    'value': SymbolKind.Variable,
    'param': SymbolKind.Variable,
    'statement': SymbolKind.Variable,
    'boolean': SymbolKind.Boolean,
    'int': SymbolKind.Number,
    'longlean': SymbolKind.Number,
    'float': SymbolKind.Number,
    'complex': SymbolKind.Number,
    'string': SymbolKind.String,
    'unicode': SymbolKind.String,
    'list': SymbolKind.Array,
    'field': SymbolKind.Field
}


def _kind(d):
    """ Return the VSCode Symbol Type """
    return _SYMBOL_KIND_MAP.get(d.type)
