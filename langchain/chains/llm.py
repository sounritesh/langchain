"""Chain that just formats a prompt and calls an LLM."""
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, Extra

from langchain.chains.base import Chain
from langchain.input import get_colored_text
from langchain.llms.base import BaseLLM
from langchain.prompts.base import BasePromptTemplate
from langchain.prompts.prompt import PromptTemplate
from langchain.schema import LLMResult


VISUAL_CHATGPT_PREFIX = """Visual ChatGPT is designed to be able to assist with a wide range of text and visual related tasks, from answering simple questions to providing in-depth explanations and discussions on a wide range of topics. Visual ChatGPT is able to generate human-like text based on the input it receives, allowing it to engage in natural-sounding conversations and provide responses that are coherent and relevant to the topic at hand.
Visual ChatGPT is able to process and understand large amounts of text and images. As a language model, Visual ChatGPT can not directly read images, but it has a list of tools to finish different visual tasks. Each image will have a file name formed as "image/xxx.png", and Visual ChatGPT can invoke different tools to indirectly understand pictures. When talking about images, Visual ChatGPT is very strict to the file name and will never fabricate nonexistent files. When using tools to generate new image files, Visual ChatGPT is also known that the image may not be the same as the user's demand, and will use other visual question answering tools or description tools to observe the real image. Visual ChatGPT is able to use tools in a sequence, and is loyal to the tool observation outputs rather than faking the image content and image file name. It will remember to provide the file name from the last tool observation, if a new image is generated.
Human may provide new figures to Visual ChatGPT with a description. The description helps Visual ChatGPT to understand this image, but Visual ChatGPT should use tools to finish following tasks, rather than directly imagine from the description.
Overall, Visual ChatGPT is a powerful visual dialogue assistant tool that can help with a wide range of tasks and provide valuable insights and information on a wide range of topics. 
TOOLS:
------
Visual ChatGPT  has access to the following tools:"""


class LLMChain(Chain, BaseModel):
    """Chain to run queries against LLMs.

    Example:
        .. code-block:: python

            from langchain import LLMChain, OpenAI, PromptTemplate
            prompt_template = "Tell me a {adjective} joke"
            prompt = PromptTemplate(
                input_variables=["adjective"], template=prompt_template
            )
            llm = LLMChain(llm=OpenAI(), prompt=prompt)
    """

    prompt: BasePromptTemplate
    """Prompt object to use."""
    llm: BaseLLM
    """LLM wrapper to use."""
    output_key: str = "text"  #: :meta private:

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def input_keys(self) -> List[str]:
        """Will be whatever keys the prompt expects.

        :meta private:
        """
        return self.prompt.input_variables

    @property
    def output_keys(self) -> List[str]:
        """Will always return text key.

        :meta private:
        """
        return [self.output_key]

    def generate(self, input_list: List[Dict[str, Any]]) -> LLMResult:
        """Generate LLM result from inputs."""
        prompts, stop = self.prep_prompts(input_list)
        # print("PROMPTS: ", prompts[0])
        response = self.llm.generate(prompts, stop=stop)
        return response

    async def agenerate(self, input_list: List[Dict[str, Any]]) -> LLMResult:
        """Generate LLM result from inputs."""
        prompts, stop = await self.aprep_prompts(input_list)
        response = await self.llm.agenerate(prompts, stop=stop)
        return response

    def prep_prompts(
        self, input_list: List[Dict[str, Any]]
    ) -> Tuple[List[str], Optional[List[str]]]:
        """Prepare prompts from inputs."""
        stop = None
        if "stop" in input_list[0]:
            stop = input_list[0]["stop"]

        prompts = []
        for inputs in input_list:
            selected_inputs = {k: inputs[k] for k in self.prompt.input_variables}
            prompt = self.prompt.format(**selected_inputs)
            _colored_text = get_colored_text(prompt, "green")
            _text = "Prompt after formatting:\n" + _colored_text
            self.callback_manager.on_text(_text, end="\n", verbose=self.verbose)
            if "stop" in inputs and inputs["stop"] != stop:
                raise ValueError(
                    "If `stop` is present in any inputs, should be present in all."
                )

            hist = inputs["chat_history"]
            # print("\nINSIDE PREP: ", inputs)
            # print(f"\n HISTORY: {hist}")
            if inputs["chat_history"] != '':
                prompt = prompt.replace(VISUAL_CHATGPT_PREFIX, '')
                # print("\n HIST PRESENT: ", prompt)
            prompts.append(prompt)
        return prompts, stop

    async def aprep_prompts(
        self, input_list: List[Dict[str, Any]]
    ) -> Tuple[List[str], Optional[List[str]]]:
        """Prepare prompts from inputs."""
        stop = None
        if "stop" in input_list[0]:
            stop = input_list[0]["stop"]
        prompts = []
        for inputs in input_list:
            selected_inputs = {k: inputs[k] for k in self.prompt.input_variables}
            prompt = self.prompt.format(**selected_inputs)
            _colored_text = get_colored_text(prompt, "green")
            _text = "Prompt after formatting:\n" + _colored_text
            if self.callback_manager.is_async:
                await self.callback_manager.on_text(
                    _text, end="\n", verbose=self.verbose
                )
            else:
                self.callback_manager.on_text(_text, end="\n", verbose=self.verbose)
            if "stop" in inputs and inputs["stop"] != stop:
                raise ValueError(
                    "If `stop` is present in any inputs, should be present in all."
                )
            prompts.append(prompt)
        return prompts, stop

    def apply(self, input_list: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Utilize the LLM generate method for speed gains."""
        response = self.generate(input_list)
        return self.create_outputs(response)

    async def aapply(self, input_list: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Utilize the LLM generate method for speed gains."""
        response = await self.agenerate(input_list)
        return self.create_outputs(response)

    def create_outputs(self, response: LLMResult) -> List[Dict[str, str]]:
        """Create outputs from response."""
        return [
            # Get the text of the top generated string.
            {self.output_key: generation[0].text}
            for generation in response.generations
        ]

    def _call(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        known_values = self.prep_inputs(inputs.copy())
        return self.apply([known_values])[0]

    async def _acall(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        known_values = self.prep_inputs(inputs.copy())
        return (await self.aapply([known_values]))[0]

    def predict(self, **kwargs: Any) -> str:
        """Format prompt with kwargs and pass to LLM.

        Args:
            **kwargs: Keys to pass to prompt template.

        Returns:
            Completion from LLM.

        Example:
            .. code-block:: python

                completion = llm.predict(adjective="funny")
        """
        return self(kwargs)[self.output_key]

    async def apredict(self, **kwargs: Any) -> str:
        """Format prompt with kwargs and pass to LLM.

        Args:
            **kwargs: Keys to pass to prompt template.

        Returns:
            Completion from LLM.

        Example:
            .. code-block:: python

                completion = llm.predict(adjective="funny")
        """
        return (await self.acall(kwargs))[self.output_key]

    def predict_and_parse(self, **kwargs: Any) -> Union[str, List[str], Dict[str, str]]:
        """Call predict and then parse the results."""
        result = self.predict(**kwargs)
        if self.prompt.output_parser is not None:
            return self.prompt.output_parser.parse(result)
        else:
            return result

    def apply_and_parse(
        self, input_list: List[Dict[str, Any]]
    ) -> Sequence[Union[str, List[str], Dict[str, str]]]:
        """Call apply and then parse the results."""
        result = self.apply(input_list)
        return self._parse_result(result)

    def _parse_result(
        self, result: List[Dict[str, str]]
    ) -> Sequence[Union[str, List[str], Dict[str, str]]]:
        if self.prompt.output_parser is not None:
            return [
                self.prompt.output_parser.parse(res[self.output_key]) for res in result
            ]
        else:
            return result

    async def aapply_and_parse(
        self, input_list: List[Dict[str, Any]]
    ) -> Sequence[Union[str, List[str], Dict[str, str]]]:
        """Call apply and then parse the results."""
        result = await self.aapply(input_list)
        return self._parse_result(result)

    @property
    def _chain_type(self) -> str:
        return "llm_chain"

    @classmethod
    def from_string(cls, llm: BaseLLM, template: str) -> Chain:
        """Create LLMChain from LLM and template."""
        prompt_template = PromptTemplate.from_template(template)
        return cls(llm=llm, prompt=prompt_template)
