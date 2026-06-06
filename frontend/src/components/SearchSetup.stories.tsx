import React from "react";
import type { Meta, StoryObj } from "@storybook/react";
import demoRoom from "../assets/demo-room.png";
import { defaultPrompt } from "../demoData";
import { SearchSetup, type SampleImageOption } from "./SearchSetup";

const meta = {
  title: "Workbench/Search Setup",
  component: SearchSetup,
  parameters: {
    docs: {
      description: {
        component:
          "The material-search intake step used as a dedicated start page and as a compact workbench rail after a run begins.",
      },
    },
  },
} satisfies Meta<typeof SearchSetup>;

export default meta;
type Story = StoryObj<typeof meta>;

function StatefulSetup(args: React.ComponentProps<typeof SearchSetup>) {
  const [prompt, setPrompt] = React.useState(args.prompt);
  const [selectedFileName, setSelectedFileName] = React.useState(args.selectedFileName);
  const [previewUrl, setPreviewUrl] = React.useState(args.previewUrl);

  const handleFileSelect = (file: File) => {
    setSelectedFileName(file.name);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleSampleSelect = (sample: SampleImageOption) => {
    setSelectedFileName(sample.name);
    setPreviewUrl(sample.src);
  };

  return (
    <SearchSetup
      {...args}
      prompt={prompt}
      selectedFileName={selectedFileName}
      previewUrl={previewUrl}
      onPromptChange={setPrompt}
      onFileSelect={handleFileSelect}
      onSampleSelect={handleSampleSelect}
      onRun={() => undefined}
    />
  );
}

export const IntakePage: Story = {
  render: (args) => <StatefulSetup {...args} />,
  args: {
    scenario: "empty",
    prompt: defaultPrompt,
    selectedFileName: undefined,
    previewUrl: undefined,
    isRunning: false,
    layout: "page",
    error: null,
    onPromptChange: () => undefined,
    onFileSelect: () => undefined,
    onSampleSelect: () => undefined,
    onRun: () => undefined,
  },
};

export const IntakePageWithImage: Story = {
  render: (args) => <StatefulSetup {...args} />,
  args: {
    ...IntakePage.args,
    selectedFileName: "hospitality-lounge-sample.png",
    previewUrl: demoRoom,
  },
};

export const WorkbenchRail: Story = {
  render: (args) => <StatefulSetup {...args} />,
  args: {
    ...IntakePage.args,
    scenario: "matching",
    selectedFileName: "hospitality-lounge-sample.png",
    previewUrl: demoRoom,
    layout: "rail",
    isRunning: true,
  },
};
