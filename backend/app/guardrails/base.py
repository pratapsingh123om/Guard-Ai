from dataclasses import dataclass
from abc import ABC ,abstractmethod

@dataclass
class GuardrailResult:
  """
  This is the exact data structre EVERY guardrail will return 
  """
  passed:bool

  action :str
  reason :str

class Guardrail(ABC):
  """
  this is blueprint
  """
  @abstractmethod
  def check(self,context:str)->GuardrailResult:
    pass