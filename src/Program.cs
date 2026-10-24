using Aetheris.CodeNativeBracket;
using static Aetheris.CodeNativeBracket.Program;

if (args.Length != 1) throw new ArgumentException("Usage: CodeNativeDesignDemo <output-directory>");
var output = Path.GetFullPath(args[0]);

// Millimetres. Edit these specifications, review the diff, let CI build the parts.
MakeCase(new BracketDimensions(
    Width: 96, Height: 60, LegWidth: 20, LegHeight: 20, Thickness: 12,
    HoleX: 76, HoleY: 10, ShaftDiameter: 6, EntryDiameter: 12),
    "nominal");

MakeCase(new BracketDimensions(
    Width: 100, Height: 75, LegWidth: 25, LegHeight: 24, Thickness: 15,
    HoleX: 70, HoleY: 12, ShaftDiameter: 8, EntryDiameter: 14),
    "variant");

void MakeCase(BracketDimensions dimensions, string name)
{
    var directory = Path.Combine(output, name);
    MakeBracket(dimensions, directory);
    var assembly = Path.Combine(directory, "assembly");
    Directory.CreateDirectory(assembly);
    foreach (var file in Directory.GetFiles(Path.Combine(AppContext.BaseDirectory, "firmament")))
        File.Copy(file, Path.Combine(assembly, Path.GetFileName(file)));

    // One parameter owner: the drawing's part and assembly receive the same values.
    // The fastener has 0.3 mm nominal diametral clearance and protrudes 4 mm.
    File.WriteAllText(Path.Combine(assembly, "parameters.firmament"), FormattableString.Invariant($$"""
        Static bracketSpec: BracketSpec = BracketSpec {
            width: {{dimensions.Width}}mm; height: {{dimensions.Height}}mm
            legWidth: {{dimensions.LegWidth}}mm; legHeight: {{dimensions.LegHeight}}mm
            thickness: {{dimensions.Thickness}}mm; holeX: {{dimensions.HoleX}}mm; holeY: {{dimensions.HoleY}}mm
            shaftDiameter: {{dimensions.ShaftDiameter}}mm; entryDiameter: {{dimensions.EntryDiameter}}mm
        }
        Static fastenerSpec: FastenerSpec = FastenerSpec {
            shaftDiameter: {{dimensions.ShaftDiameter - 0.3}}mm
            headDiameter: {{dimensions.EntryDiameter}}mm
            length: {{dimensions.Thickness + 4}}mm
            tipChamfer: 0.5mm
        }
        """));
}
