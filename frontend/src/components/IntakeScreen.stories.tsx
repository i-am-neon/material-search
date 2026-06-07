import type { Meta, StoryObj } from "@storybook/react";
import { IntakeScreen } from "./IntakeScreen";

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
    onPickSample: () => {},
    onRun: () => {},
  },
};
export default meta;
type Story = StoryObj<typeof IntakeScreen>;

export const Empty: Story = {};
export const WithFile: Story = { args: { selectedFileName: "room.png" } };
export const Running: Story = { args: { selectedFileName: "room.png", isRunning: true } };
export const WithError: Story = { args: { error: "Choose a reference image before running search." } };
