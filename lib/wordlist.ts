// Shared word lists for readable random names (used by the API and the workbench).
export const ADJECTIVES = ["amber", "brisk", "calm", "cedar", "clear", "coral", "crisp", "dawn", "deep", "ember", "fair", "fern", "golden", "granite", "hazel", "ivory", "jade", "keen", "lucid", "maple", "misty", "noble", "north", "oak", "olive", "pale", "quiet", "rapid", "river", "sage", "silver", "slate", "solar", "steady", "stone", "swift", "tidal", "true", "velvet", "vivid", "warm", "wild"];
export const NOUNS = ["atlas", "beacon", "birch", "canyon", "comet", "delta", "falcon", "fjord", "forge", "garden", "glacier", "harbor", "heron", "horizon", "island", "lantern", "ledger", "meadow", "mesa", "orbit", "otter", "pine", "prairie", "quarry", "raven", "reef", "ridge", "summit", "tern", "thicket", "tide", "trail", "valley", "vista", "willow", "wren"];
export function names(rand: (n: number) => number) {
  const pick = (a: string[]) => a[rand(a.length)];
  return {
    store: () => `${pick(ADJECTIVES)}-${pick(NOUNS)}-${10 + rand(90)}`,
    workspace: () => [pick(ADJECTIVES), pick(NOUNS)].map((w) => w[0].toUpperCase() + w.slice(1)).join(" "),
  };
}
