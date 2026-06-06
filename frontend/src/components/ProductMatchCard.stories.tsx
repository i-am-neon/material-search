import type { Meta, StoryObj } from "@storybook/react";
import { matchesByRegion } from "../demoData";
import { ProductMatchCard } from "./ProductMatchCard";

const meta = {
  title: "Results/Product Match Card",
  component: ProductMatchCard,
  args: {
    onToggleCart: () => undefined,
  },
  parameters: {
    layout: "centered",
  },
  decorators: [
    (Story) => (
      <div style={{ width: "min(430px, calc(100vw - 32px))" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ProductMatchCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Addable: Story = {
  args: {
    match: matchesByRegion["walnut-panels"][0],
    inCart: false,
  },
};

export const InCart: Story = {
  args: {
    match: matchesByRegion["sage-fabric"][0],
    inCart: true,
  },
};
