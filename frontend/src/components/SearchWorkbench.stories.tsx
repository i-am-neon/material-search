import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { SearchWorkbench } from "./SearchWorkbench";

const meta = {
  title: "Workbench/Search Workbench",
  component: SearchWorkbench,
  decorators: [
    (Story) => (
      <MemoryRouter>
        <Story />
      </MemoryRouter>
    ),
  ],
  parameters: {
    docs: {
      description: {
        component:
          "The primary material search workbench: image upload, run state, region review, catalog matches, and sample-cart actions.",
      },
    },
  },
} satisfies Meta<typeof SearchWorkbench>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Complete: Story = {
  args: {
    initialScenario: "complete",
  },
};

export const Empty: Story = {
  args: {
    initialScenario: "empty",
  },
};

export const Planning: Story = {
  args: {
    initialScenario: "planning",
  },
};

export const Matching: Story = {
  args: {
    initialScenario: "matching",
  },
};

export const Failed: Story = {
  args: {
    initialScenario: "failed",
  },
};
