import random

from .vdtui import *

option('confirm_overwrite', True, 'whether to prompt for overwrite confirmation on save')
option('headerlines', 1, 'parse first N rows of .csv/.tsv as column names')
option('skiplines', 0, 'skip first N lines of text input')
option('filetype', '', 'specify file type')

# slide rows/columns around
globalCommand('H', 'moveVisibleCol(cursorVisibleColIndex, max(cursorVisibleColIndex-1, 0)); sheet.cursorVisibleColIndex -= 1', 'move this column one left')
globalCommand('J', 'sheet.cursorRowIndex = moveListItem(rows, cursorRowIndex, min(cursorRowIndex+1, nRows-1))', 'move this row one down')
globalCommand('K', 'sheet.cursorRowIndex = moveListItem(rows, cursorRowIndex, max(cursorRowIndex-1, 0))', 'move this row one up')
globalCommand('L', 'moveVisibleCol(cursorVisibleColIndex, min(cursorVisibleColIndex+1, nVisibleCols-1)); sheet.cursorVisibleColIndex += 1', 'move this column one right')
globalCommand('gH', 'moveListItem(columns, cursorColIndex, nKeys)', 'move this column all the way to the left of the non-key columns')
globalCommand('gJ', 'moveListItem(rows, cursorRowIndex, nRows)', 'move this row all the way to the bottom')
globalCommand('gK', 'moveListItem(rows, cursorRowIndex, 0)', 'move this row all the way to the top')
globalCommand('gL', 'moveListItem(columns, cursorColIndex, nCols)', 'move this column all the way to the right')

globalCommand('c', 'searchColumnNameRegex(input("column name regex: ", "regex"), moveCursor=True)', 'go to visible column by regex of name')
globalCommand('r', 'moveRegex(regex=input("row key regex: ", "regex"), columns=keyCols or [visibleCols[0]])', 'go to row by regex of key columns')
globalCommand('zc', 'sheet.cursorVisibleColIndex = int(input("column number: "))', 'go to visible column number')
globalCommand('zr', 'sheet.cursorRowIndex = int(input("row number: "))', 'go to row number')

globalCommand('P', 'nrows=int(input("random population size: ")); vs=vd.push(copy(sheet)); vs.name+="_sample"; vs.rows=random.sample(rows, nrows)', 'push duplicate sheet with a random sample of <N> rows')

globalCommand('a', 'rows.insert(cursorRowIndex+1, list((None for c in columns))); cursorDown(1)', 'insert a blank row')
globalCommand('g^', 'for c in visibleCols: c.name = c.getDisplayValue(cursorRow)', 'set names of all visible columns to this row')

globalCommand('o', 'vd.push(openSource(input("open: ", "filename")))', 'open local file or url')
globalCommand('^S', 'saveSheet(sheet, input("save to: ", "filename", value=name+".tsv"), options.confirm_overwrite)', 'save this sheet to new file')

globalCommand('z=', 'status(evalexpr(input("status=", "expr"), cursorRow))', 'show evaluated expression over current row')

globalCommand('A', 'vd.push(newSheet(int(input("num columns for new sheet: "))))', 'create new sheet with N columns')

alias('gKEY_F(1)', 'z?')  # vdtui generic commands sheet
alias('gz?', 'z?')  # vdtui generic commands sheet

# in VisiData, F1/z? refer to the man page
globalCommand('z?', 'with suspend_curses(): os.system("man vd")', 'launch VisiData manpage')
alias('KEY_F(1)', 'z?')

def newSheet(ncols):
    return Sheet('unnamed', columns=[ColumnItem('', i, width=8) for i in range(ncols)])

def readlines(linegen):
    'Generate lines from linegen, skipping first options.skiplines lines and stripping trailing newline'
    skiplines = options.skiplines
    for i, line in enumerate(linegen):
        if i < skiplines:
            continue
        yield line[:-1]


def saveSheet(vs, fn, confirm_overwrite=False):
    'Save sheet `vs` with given filename `fn`.'
    if Path(fn).exists():
        if options.confirm_overwrite:
            confirm('%s already exists. overwrite? ' % fn)

    basename, ext = os.path.splitext(fn)
    funcname = 'save_' + ext[1:]
    if funcname not in getGlobals():
        funcname = 'save_tsv'
    getGlobals().get(funcname)(vs, fn)
    status('saving to ' + fn)


class DirSheet(Sheet):
    'Sheet displaying directory, using ENTER to open a particular file.'
    commands = [
        Command(ENTER, 'vd.push(openSource(cursorRow[0]))', 'open file')  # path, filename
    ]
    columns = [
        Column('filename', getter=lambda r: r[0].name + r[0].ext),
        Column('type', getter=lambda r: r[0].is_dir() and '/' or r[0].suffix),
        Column('size', type=int, getter=lambda r: r[1].st_size),
        Column('mtime', type=date, getter=lambda r: r[1].st_mtime)
    ]

    def reload(self):
        self.rows = [(p, p.stat()) for p in self.source.iterdir()]  #  if not p.name.startswith('.')]


def openSource(p, filetype=None):
    'calls open_ext(Path) or openurl_scheme(url)'
    if isinstance(p, str):
        if '://' in p:
            p = UrlPath(p)
            openfunc = 'openurl_' + (filetype or p.scheme)
            vs = getGlobals()[openfunc](p)
        else:
            return openSource(Path(p), filetype)  # convert to Path and recurse
    elif isinstance(p, Path):
        if not filetype:
            filetype = options.filetype or p.suffix

        if os.path.isdir(p.resolve()):
            vs = DirSheet(p.name, p)
            filetype = 'dir'
        else:
            openfunc = 'open_' + filetype.lower()
            if openfunc not in getGlobals():
                status('no %s function' % openfunc)
                filetype = 'txt'
                openfunc = 'open_txt'
            vs = getGlobals()[openfunc](p)
    else:  # some other object
        status('unknown object type %s' % type(p))
        vs = None

    if vs:
        status('opening %s as %s' % (p.name, filetype))
        vs.recalc()  # set col.sheet

    return vs

#### enable external addons
def open_vd(p):
    'Opens a .vd file as a .tsv file'
    vs = open_tsv(p)
    vs.reload()
    return vs

def open_py(p):
    'Load a .py addon into the global context.'
    contents = p.read_text()
    exec(contents, getGlobals())
    status('executed %s' % p)

def open_txt(p):
    'Create sheet from `.txt` file at Path `p`, checking whether it is TSV.'
    with p.open_text() as fp:
        if '\t' in next(fp):    # peek at the first line
            return open_tsv(p)  # TSV often have .txt extension
        return TextSheet(p.name, p)

def _getTsvHeaders(fp, nlines):
    headers = []
    i = 0
    while i < nlines:
        L = next(fp)
        L = L[:-1]
        if L:
            headers.append(L.split('\t'))
            i += 1

    return headers

def open_tsv(p, vs=None):
    'Parse contents of Path `p` and populate columns.'

    if vs is None:
        vs = Sheet(p.name, p)
        vs.loader = lambda vs=vs: reload_tsv(vs)

    header_lines = int(options.headerlines)

    with vs.source.open_text() as fp:
        headers = _getTsvHeaders(fp, header_lines or 1)  # get one data line if no headers

        if header_lines == 0:
            vs.columns = ArrayColumns(len(headers[0]))
        else:
            # columns ideally reflect the max number of fields over all rows
            # but that's a lot of work for a large dataset
            vs.columns = ArrayNamedColumns('\\n'.join(x) for x in zip(*headers[:header_lines]))

    return vs

@async
def reload_tsv(vs):
    'Asynchronous wrapper for `reload_tsv_sync`.'
    reload_tsv_sync(vs)

def reload_tsv_sync(vs):
    'Perform synchronous loading of TSV file, discarding header lines.'
    header_lines = int(options.headerlines)

    vs.rows = []
    with vs.source.open_text() as fp:
        _getTsvHeaders(fp, header_lines)  # discard header lines

        vs.progressMade = 0
        vs.progressTotal = vs.source.filesize
        while True:
            try:
                L = next(fp)
            except StopIteration:
                break
            L = L[:-1]
            if L:
                vs.addRow(L.split('\t'))
            vs.progressMade += len(L)

    vs.progressMade = 0
    vs.progressTotal = 0

    status('loaded %s' % vs.name)


@async
def save_tsv(vs, fn):
    'Write sheet to file `fn` as TSV.'

    # replace tabs and newlines
    replch = options.disp_oddspace
    trdict = {9: replch, 10: replch, 13: replch}

    with open(fn, 'w', encoding=options.encoding, errors=options.encoding_errors) as fp:
        colhdr = '\t'.join(col.name.translate(trdict) for col in vs.visibleCols) + '\n'
        if colhdr.strip():  # is anything but whitespace
            fp.write(colhdr)
        for r in vs.genProgress(vs.rows):
            fp.write('\t'.join(col.getDisplayValue(r).translate(trdict) for col in vs.visibleCols) + '\n')
    status('%s save finished' % fn)

