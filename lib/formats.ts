/** Validated source formats (advertise only what passes tests in py/tests and tests/api.test.mjs). */
export const FORMATS: Record<string, { media_type: string; modality: string; location: string }> = {
  ".txt": { media_type: "text/plain", modality: "text", location: "char offsets" },
  ".md": { media_type: "text/markdown", modality: "text", location: "char offsets" },
  ".markdown": { media_type: "text/markdown", modality: "text", location: "char offsets" },
  ".pdf": { media_type: "application/pdf", modality: "text|image", location: "page" },
  ".docx": { media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", modality: "text", location: "char offsets + section heading" },
  ".jpg": { media_type: "image/jpeg", modality: "image", location: "whole image" },
  ".jpeg": { media_type: "image/jpeg", modality: "image", location: "whole image" },
  ".png": { media_type: "image/png", modality: "image", location: "whole image" },
  ".wav": { media_type: "audio/wav", modality: "audio", location: "start/end seconds" },
  ".mp3": { media_type: "audio/mpeg", modality: "audio", location: "start/end seconds" },
  ".mp4": { media_type: "video/mp4", modality: "video", location: "start/end seconds" },
};
export const QUERY_ASSET_TYPES = ["image/jpeg", "image/png", "audio/wav", "audio/mpeg", "video/mp4"];
export function mediaTypeFor(path: string): string | null {
  const m = /\.[^./]+$/.exec(path.toLowerCase());
  return (m && FORMATS[m[0]]?.media_type) || null;
}
