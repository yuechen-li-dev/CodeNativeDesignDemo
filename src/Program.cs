using Aetheris.CodeNativeBracket;
using static Aetheris.CodeNativeBracket.Program;

if (args.Length != 1) throw new ArgumentException("Usage: CodeNativeDesignDemo <output-directory>");
var output = Path.GetFullPath(args[0]);

// Millimetres. Edit these specifications, review the diff, let CI build the parts.
MakeBracket(new BracketDimensions(
    Width: 96, Height: 60, LegWidth: 20, LegHeight: 20, Thickness: 12,
    HoleX: 76, HoleY: 10, ShaftDiameter: 6, EntryDiameter: 12),
    Path.Combine(output, "nominal"));

MakeBracket(new BracketDimensions(
    Width: 100, Height: 75, LegWidth: 25, LegHeight: 24, Thickness: 15,
    HoleX: 70, HoleY: 12, ShaftDiameter: 8, EntryDiameter: 14),
    Path.Combine(output, "variant"));
