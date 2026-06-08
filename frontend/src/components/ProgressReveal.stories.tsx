import type { Meta, StoryObj } from "@storybook/react";
import { useEffect, useState } from "react";
import { ProgressReveal } from "./ProgressReveal";
import {
  completeFrame,
  matchingFrame,
  planningFrame,
  progressFrames,
  segmentingFrame,
} from "../progressDemo";
import bathroomTall from "../assets/bathroom-tall.webp";

const meta: Meta<typeof ProgressReveal> = {
  title: "Studio/ProgressReveal",
  component: ProgressReveal,
  parameters: { layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof ProgressReveal>;

// Static frames — one per pipeline stage.
export const Planning: Story = { args: { snapshot: planningFrame } };
export const Segmenting: Story = { args: { snapshot: segmentingFrame } };
export const Matching: Story = { args: { snapshot: matchingFrame } };
export const Complete: Story = { args: { snapshot: completeFrame } };
export const TallBathroom: Story = {
  args: {
    snapshot: {
      ...matchingFrame,
      previewUrl: bathroomTall,
      imageWidth: 513,
      imageHeight: 640,
    },
  },
};

// Animated playthrough — steps through the whole reveal on a timer, then loops.
// Lets us iterate on the staged animation with no real backend calls.
export const Playthrough: Story = {
  render: () => {
    const [index, setIndex] = useState(0);
    useEffect(() => {
      const isComplete = index >= progressFrames.length - 1;
      const timer = setTimeout(() => setIndex((i) => (i + 1) % progressFrames.length), isComplete ? 2200 : 850);
      return () => clearTimeout(timer);
    }, [index]);
    return <ProgressReveal snapshot={progressFrames[index]} />;
  },
};
