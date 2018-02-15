from visidata import *


def open_ttf(p):
    return TTFTablesSheet(p.name, source=p)

open_otf = open_ttf

class TTFTablesSheet(Sheet):
    rowtype = 'font tables'
    columns = [
        ColumnAttr('cmap'),
        ColumnAttr('format', type=int),
        ColumnAttr('language', type=int),
        ColumnAttr('length', type=int),
        ColumnAttr('platEncID', type=int),
        ColumnAttr('platformID', type=int),
        Column('isSymbol', getter=lambda col,row: row.isSymbol()),
        Column('isUnicode', getter=lambda col,row: row.isUnicode()),
    ]
    commands = [
        Command(ENTER, 'vd.push(TTFGlyphsSheet(name+str(cursorRowIndex), source=sheet, sourceRows=[cursorRow], ttf=ttf))', '', ''),
    ]

    @async
    def reload(self):
        import fontTools.ttLib

        self.ttf = fontTools.ttLib.TTFont(self.source.resolve(), 0, allowVID=0, ignoreDecompileErrors=True, fontNumber=-1)
        self.rows = []
        for cmap in self.ttf["cmap"].tables:
            self.addRow(cmap)


class TTFGlyphsSheet(Sheet):
    rowtype = 'glyphs'  # rowdef: (codepoint, glyphid, fontTools.ttLib.ttFont._TTGlyphGlyf)
    columns = [
        ColumnItem('codepoint', 0, type=int, fmtstr='{:X}'),
        ColumnItem('glyphid', 1),
        SubrowColumn(ColumnAttr('height', type=int), 2),
        SubrowColumn(ColumnAttr('width', type=int), 2),
        SubrowColumn(ColumnAttr('lsb'), 2),
        SubrowColumn(ColumnAttr('tsb'), 2),
    ]
    commands = [
        Command('.', 'vd.push(GlyphPen(name+"_"+cursorRow[1], source=cursorRow[2]))', 'push plot of this glyph')
    ]
    @async
    def reload(self):
        self.rows = []
        glyphs = self.ttf.getGlyphSet()
        for cmap in self.sourceRows:
            for codepoint, glyphid in Progress(cmap.cmap.items(), total=len(cmap.cmap)):
                self.addRow((codepoint, glyphid, glyphs[glyphid]))


class GlyphPen(InvertedCanvas):
    aspectRatio = 1.0
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.firstxy = None
        self.lastxy = None
        self.attr = self.plotColor(('line',))
    def moveTo(self, xy):
        self.lastxy = xy
    def lineTo(self, xy):
        if not self.firstxy: self.firstxy = self.lastxy
        x1, y1 = self.lastxy
        x2, y2 = xy
        self.line(x1, y1, x2, y2, self.attr)
        self.lastxy = xy
    def closePath(self):
        self.lineTo(self.firstxy)
        self.firstxy = None
        self.lastxy = None
    def qCurveTo(self, *pts):
        if not self.firstxy: self.firstxy = self.lastxy
        self.curve([self.lastxy] + list(pts), self.plotColor(('curve',)))
        self.lastxy = pts[-1]
    def curveTo(self, *pts):
        if not self.firstxy: self.firstxy = self.lastxy
        self.curve([self.lastxy] + list(pts), self.plotColor(('curve',)))
        self.lastxy = pts[-1]
    def reload(self):
        self.reset()
        self.source.draw(self)
        self.refresh()
