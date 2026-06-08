export type ImageDimensions = {
  width: number;
  height: number;
};

export function measureImageDimensions(src: string): Promise<ImageDimensions> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const width = image.naturalWidth || image.width;
      const height = image.naturalHeight || image.height;
      if (width > 0 && height > 0) resolve({ width, height });
      else reject(new Error("Image dimensions unavailable"));
    };
    image.onerror = () => reject(new Error("Could not load image dimensions"));
    image.src = src;
  });
}
