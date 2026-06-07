import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { SearchWorkbench } from "./SearchWorkbench";

const meta: Meta<typeof SearchWorkbench> = {
  title: "Studio/SearchWorkbench",
  component: SearchWorkbench,
  parameters: { layout: "fullscreen" },
  decorators: [(S) => <MemoryRouter><S /></MemoryRouter>],
};
export default meta;
type Story = StoryObj<typeof SearchWorkbench>;

export const Intake: Story = { args: { initialScenario: "empty" } };
export const Studio: Story = { args: { initialScenario: "complete" } };
