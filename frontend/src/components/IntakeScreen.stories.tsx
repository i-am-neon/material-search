import type { Meta, StoryObj } from "@storybook/react";
import { IntakeScreen } from "./IntakeScreen";
import demoBathroom from "../assets/demo-bathroom.png";

const meta: Meta<typeof IntakeScreen> = {
  title: "Studio/IntakeScreen",
  component: IntakeScreen,
  parameters: { layout: "fullscreen" },
  args: {
    prompt: "a warm matte floor tile",
    isRunning: false,
    error: null,
    onPromptChange: () => {},
    onPickFile: () => {},
    onRun: () => {},
  },
};
export default meta;
type Story = StoryObj<typeof IntakeScreen>;

export const Empty: Story = {};
export const WithFile: Story = {
  args: {
    selectedFileName: "green-shower-bath-sample.png",
    previewUrl: demoBathroom,
    imageWidth: 513,
    imageHeight: 640,
  },
};
export const Running: Story = {
  args: {
    selectedFileName: "green-shower-bath-sample.png",
    previewUrl: demoBathroom,
    imageWidth: 513,
    imageHeight: 640,
    isRunning: true,
  },
};
export const WithError: Story = { args: { error: "Choose a reference image before running search." } };
