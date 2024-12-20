from application.core.settings import settings
from application.retriever.base import BaseRetriever
from application.tools.agent import Agent

from application.utils import num_tokens_from_string
from application.vectorstore.vector_creator import VectorCreator



class ClassicRAG(BaseRetriever):

    def __init__(
        self,
        question,
        source,
        chat_history,
        prompt,
        chunks=2,
        token_limit=150,
        gpt_model="docsgpt",
        user_api_key=None,
    ):
        self.question = question
        self.vectorstore = source["active_docs"] if "active_docs" in source else None
        self.chat_history = chat_history
        self.prompt = prompt
        self.chunks = chunks
        self.gpt_model = gpt_model
        self.token_limit = (
            token_limit
            if token_limit
            < settings.MODEL_TOKEN_LIMITS.get(
                self.gpt_model, settings.DEFAULT_MAX_HISTORY
            )
            else settings.MODEL_TOKEN_LIMITS.get(
                self.gpt_model, settings.DEFAULT_MAX_HISTORY
            )
        )
        self.user_api_key = user_api_key

    def _get_data(self):
        if self.chunks == 0:
            docs = []
        else:
            docsearch = VectorCreator.create_vectorstore(
                settings.VECTOR_STORE, self.vectorstore, settings.EMBEDDINGS_KEY
            )
            docs_temp = docsearch.search(self.question, k=self.chunks)
            docs = [
                {
                    "title": i.metadata.get(
                        "title", i.metadata.get("post_title", i.page_content)
                    ).split("/")[-1],
                    "text": i.page_content,
                    "source": (
                        i.metadata.get("source")
                        if i.metadata.get("source")
                        else "local"
                    ),
                }
                for i in docs_temp
            ]

        return docs

    def gen(self):
        docs = self._get_data()

        # join all page_content together with a newline
        docs_together = "\n".join([doc["text"] for doc in docs])
        p_chat_combine = self.prompt.replace("{summaries}", docs_together)
        messages_combine = [{"role": "system", "content": p_chat_combine}]
        for doc in docs:
            yield {"source": doc}

        if len(self.chat_history) > 1:
            for i in self.chat_history:
                    if "prompt" in i and "response" in i:
                        messages_combine.append(
                            {"role": "user", "content": i["prompt"]}
                        )
                        messages_combine.append(
                            {"role": "system", "content": i["response"]}
                        )
        messages_combine.append({"role": "user", "content": self.question})
        # llm = LLMCreator.create_llm(
        #     settings.LLM_NAME, api_key=settings.API_KEY, user_api_key=self.user_api_key
        # )
        # completion = llm.gen_stream(model=self.gpt_model, messages=messages_combine)
        agent = Agent(
            llm_name=settings.LLM_NAME,
            gpt_model=self.gpt_model,
            api_key=settings.API_KEY,
            user_api_key=self.user_api_key,
        )
        completion = agent.gen(messages_combine)
        for line in completion:
            yield {"answer": str(line)}

    def search(self):
        return self._get_data()

    def get_params(self):
        return {
            "question": self.question,
            "source": self.vectorstore,
            "chat_history": self.chat_history,
            "prompt": self.prompt,
            "chunks": self.chunks,
            "token_limit": self.token_limit,
            "gpt_model": self.gpt_model,
            "user_api_key": self.user_api_key,
        }
