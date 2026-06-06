import type { Meta, StoryObj } from "@storybook/react";
import { getRunStages } from "../demoData";
import { RunTimeline } from "./RunTimeline";

const meta = {
  title: "Workflow/Run Timeline",
  component: RunTimeline,
  parameters: {
    layout: "centered",
  },
  decorators: [
    (Story) => (
      <div style={{ width: "min(900px, calc(100vw - 32px))" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof RunTimeline>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Complete: Story = {
  args: {
    stages: getRunStages("complete"),
    runLabel: "RUN-2406",
  },
};

export const Failed: Story = {
  args: {
    stages: getRunStages("failed"),
    runLabel: "RUN-2406-F",
  },
};
