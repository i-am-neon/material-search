import demoRoom from "./assets/demo-room.png";

export type SampleImageOption = {
  id: string;
  name: string;
  src: string;
  filename: string;
};

export const sampleImages: SampleImageOption[] = [
  {
    id: "hospitality-lounge",
    name: "Hospitality lounge",
    src: demoRoom,
    filename: "hospitality-lounge-sample.png",
  },
];

export async function fileFromSample(sample: SampleImageOption): Promise<File> {
  const response = await fetch(sample.src);
  if (!response.ok) {
    throw new Error(`Could not load sample image ${sample.id}`);
  }
  const blob = await response.blob();
  return new File([blob], sample.filename, { type: blob.type || "image/png" });
}
