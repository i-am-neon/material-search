import type { Meta, StoryObj } from "@storybook/react";
import { AnalysisReveal } from "./AnalysisReveal";
import demoRoom from "../assets/demo-room.png";

const meta: Meta<typeof AnalysisReveal> = {
  title: "Studio/AnalysisReveal",
  component: AnalysisReveal,
  parameters: { layout: "fullscreen" },
  args: { previewUrl: demoRoom, imageWidth: 1536, imageHeight: 1024, onRetry: () => {}, onReset: () => {} },
};
export default meta;
type Story = StoryObj<typeof AnalysisReveal>;

export const Analyzing: Story = { args: { mode: "analyzing", error: null } };
export const Failed: Story = { args: { mode: "failed", error: "Segmenter timed out" } };
