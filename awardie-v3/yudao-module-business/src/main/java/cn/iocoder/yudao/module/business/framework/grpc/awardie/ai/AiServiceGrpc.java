package cn.iocoder.yudao.module.business.framework.grpc.awardie.ai;

import static io.grpc.MethodDescriptor.generateFullMethodName;

/**
 * <pre>
 * AI Worker 契约(v1 LangGraph 编排 1:1 保留,仅接口层 gRPC 化,N1 非目标)
 * 流式口径与探针 P1 结论一致:server-streaming 走 Nginx 需 grpc_read_timeout&gt;=300s。
 * </pre>
 */
@javax.annotation.Generated(
    value = "by gRPC proto compiler (version 1.64.0)",
    comments = "Source: ai_service.proto")
@io.grpc.stub.annotations.GrpcGenerated
public final class AiServiceGrpc {

  private AiServiceGrpc() {}

  public static final java.lang.String SERVICE_NAME = "awardie.ai.AiService";

  // Static method descriptors that strictly reflect the proto.
  private static volatile io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse> getExtractMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "Extract",
      requestType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest.class,
      responseType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse> getExtractMethod() {
    io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse> getExtractMethod;
    if ((getExtractMethod = AiServiceGrpc.getExtractMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getExtractMethod = AiServiceGrpc.getExtractMethod) == null) {
          AiServiceGrpc.getExtractMethod = getExtractMethod =
              io.grpc.MethodDescriptor.<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "Extract"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse.getDefaultInstance()))
              .setSchemaDescriptor(new AiServiceMethodDescriptorSupplier("Extract"))
              .build();
        }
      }
    }
    return getExtractMethod;
  }

  private static volatile io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse> getExtractTemplateMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ExtractTemplate",
      requestType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest.class,
      responseType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse> getExtractTemplateMethod() {
    io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse> getExtractTemplateMethod;
    if ((getExtractTemplateMethod = AiServiceGrpc.getExtractTemplateMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getExtractTemplateMethod = AiServiceGrpc.getExtractTemplateMethod) == null) {
          AiServiceGrpc.getExtractTemplateMethod = getExtractTemplateMethod =
              io.grpc.MethodDescriptor.<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ExtractTemplate"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse.getDefaultInstance()))
              .setSchemaDescriptor(new AiServiceMethodDescriptorSupplier("ExtractTemplate"))
              .build();
        }
      }
    }
    return getExtractTemplateMethod;
  }

  private static volatile io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse> getGeneratePromptMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "GeneratePrompt",
      requestType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest.class,
      responseType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse> getGeneratePromptMethod() {
    io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse> getGeneratePromptMethod;
    if ((getGeneratePromptMethod = AiServiceGrpc.getGeneratePromptMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getGeneratePromptMethod = AiServiceGrpc.getGeneratePromptMethod) == null) {
          AiServiceGrpc.getGeneratePromptMethod = getGeneratePromptMethod =
              io.grpc.MethodDescriptor.<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "GeneratePrompt"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse.getDefaultInstance()))
              .setSchemaDescriptor(new AiServiceMethodDescriptorSupplier("GeneratePrompt"))
              .build();
        }
      }
    }
    return getGeneratePromptMethod;
  }

  private static volatile io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent> getExtractAndReviewMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ExtractAndReview",
      requestType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest.class,
      responseType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent.class,
      methodType = io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
  public static io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent> getExtractAndReviewMethod() {
    io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent> getExtractAndReviewMethod;
    if ((getExtractAndReviewMethod = AiServiceGrpc.getExtractAndReviewMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getExtractAndReviewMethod = AiServiceGrpc.getExtractAndReviewMethod) == null) {
          AiServiceGrpc.getExtractAndReviewMethod = getExtractAndReviewMethod =
              io.grpc.MethodDescriptor.<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ExtractAndReview"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent.getDefaultInstance()))
              .setSchemaDescriptor(new AiServiceMethodDescriptorSupplier("ExtractAndReview"))
              .build();
        }
      }
    }
    return getExtractAndReviewMethod;
  }

  private static volatile io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent> getAskMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "Ask",
      requestType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest.class,
      responseType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent.class,
      methodType = io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
  public static io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent> getAskMethod() {
    io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent> getAskMethod;
    if ((getAskMethod = AiServiceGrpc.getAskMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getAskMethod = AiServiceGrpc.getAskMethod) == null) {
          AiServiceGrpc.getAskMethod = getAskMethod =
              io.grpc.MethodDescriptor.<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "Ask"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent.getDefaultInstance()))
              .setSchemaDescriptor(new AiServiceMethodDescriptorSupplier("Ask"))
              .build();
        }
      }
    }
    return getAskMethod;
  }

  private static volatile io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse> getHealthMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "Health",
      requestType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest.class,
      responseType = cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest,
      cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse> getHealthMethod() {
    io.grpc.MethodDescriptor<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse> getHealthMethod;
    if ((getHealthMethod = AiServiceGrpc.getHealthMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getHealthMethod = AiServiceGrpc.getHealthMethod) == null) {
          AiServiceGrpc.getHealthMethod = getHealthMethod =
              io.grpc.MethodDescriptor.<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest, cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "Health"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse.getDefaultInstance()))
              .setSchemaDescriptor(new AiServiceMethodDescriptorSupplier("Health"))
              .build();
        }
      }
    }
    return getHealthMethod;
  }

  /**
   * Creates a new async stub that supports all call types for the service
   */
  public static AiServiceStub newStub(io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<AiServiceStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<AiServiceStub>() {
        @java.lang.Override
        public AiServiceStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new AiServiceStub(channel, callOptions);
        }
      };
    return AiServiceStub.newStub(factory, channel);
  }

  /**
   * Creates a new blocking-style stub that supports unary and streaming output calls on the service
   */
  public static AiServiceBlockingStub newBlockingStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<AiServiceBlockingStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<AiServiceBlockingStub>() {
        @java.lang.Override
        public AiServiceBlockingStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new AiServiceBlockingStub(channel, callOptions);
        }
      };
    return AiServiceBlockingStub.newStub(factory, channel);
  }

  /**
   * Creates a new ListenableFuture-style stub that supports unary calls on the service
   */
  public static AiServiceFutureStub newFutureStub(
      io.grpc.Channel channel) {
    io.grpc.stub.AbstractStub.StubFactory<AiServiceFutureStub> factory =
      new io.grpc.stub.AbstractStub.StubFactory<AiServiceFutureStub>() {
        @java.lang.Override
        public AiServiceFutureStub newStub(io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
          return new AiServiceFutureStub(channel, callOptions);
        }
      };
    return AiServiceFutureStub.newStub(factory, channel);
  }

  /**
   * <pre>
   * AI Worker 契约(v1 LangGraph 编排 1:1 保留,仅接口层 gRPC 化,N1 非目标)
   * 流式口径与探针 P1 结论一致:server-streaming 走 Nginx 需 grpc_read_timeout&gt;=300s。
   * </pre>
   */
  public interface AsyncService {

    /**
     * <pre>
     * 抽取:文件 → 结构化数据(unary,v1 framework.extract 同步语义)
     * </pre>
     */
    default void extract(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getExtractMethod(), responseObserver);
    }

    /**
     * <pre>
     * 模板抽取:样本图 → 强制 award 抽取器的结构化字段(unary,架构票;v1 extract-for-create 语义)
     * </pre>
     */
    default void extractTemplate(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getExtractTemplateMethod(), responseObserver);
    }

    /**
     * <pre>
     * 模板 prompt 生成:模板规则+样本文本 → 提示词(unary,架构票;v1 generate-prompt-for-create 语义)
     * </pre>
     */
    default void generatePrompt(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getGeneratePromptMethod(), responseObserver);
    }

    /**
     * <pre>
     * 抽取+审核全链:流式过程事件(node 进度/答案增量)+ 最终审核结论(server-streaming)
     * </pre>
     */
    default void extractAndReview(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getExtractAndReviewMethod(), responseObserver);
    }

    /**
     * <pre>
     * AI 问答(RAG):流式答案增量(server-streaming)
     * </pre>
     */
    default void ask(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getAskMethod(), responseObserver);
    }

    /**
     * <pre>
     * 健康探针
     * </pre>
     */
    default void health(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getHealthMethod(), responseObserver);
    }
  }

  /**
   * Base class for the server implementation of the service AiService.
   * <pre>
   * AI Worker 契约(v1 LangGraph 编排 1:1 保留,仅接口层 gRPC 化,N1 非目标)
   * 流式口径与探针 P1 结论一致:server-streaming 走 Nginx 需 grpc_read_timeout&gt;=300s。
   * </pre>
   */
  public static abstract class AiServiceImplBase
      implements io.grpc.BindableService, AsyncService {

    @java.lang.Override public final io.grpc.ServerServiceDefinition bindService() {
      return AiServiceGrpc.bindService(this);
    }
  }

  /**
   * A stub to allow clients to do asynchronous rpc calls to service AiService.
   * <pre>
   * AI Worker 契约(v1 LangGraph 编排 1:1 保留,仅接口层 gRPC 化,N1 非目标)
   * 流式口径与探针 P1 结论一致:server-streaming 走 Nginx 需 grpc_read_timeout&gt;=300s。
   * </pre>
   */
  public static final class AiServiceStub
      extends io.grpc.stub.AbstractAsyncStub<AiServiceStub> {
    private AiServiceStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected AiServiceStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new AiServiceStub(channel, callOptions);
    }

    /**
     * <pre>
     * 抽取:文件 → 结构化数据(unary,v1 framework.extract 同步语义)
     * </pre>
     */
    public void extract(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getExtractMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 模板抽取:样本图 → 强制 award 抽取器的结构化字段(unary,架构票;v1 extract-for-create 语义)
     * </pre>
     */
    public void extractTemplate(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getExtractTemplateMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 模板 prompt 生成:模板规则+样本文本 → 提示词(unary,架构票;v1 generate-prompt-for-create 语义)
     * </pre>
     */
    public void generatePrompt(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getGeneratePromptMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 抽取+审核全链:流式过程事件(node 进度/答案增量)+ 最终审核结论(server-streaming)
     * </pre>
     */
    public void extractAndReview(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent> responseObserver) {
      io.grpc.stub.ClientCalls.asyncServerStreamingCall(
          getChannel().newCall(getExtractAndReviewMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * AI 问答(RAG):流式答案增量(server-streaming)
     * </pre>
     */
    public void ask(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent> responseObserver) {
      io.grpc.stub.ClientCalls.asyncServerStreamingCall(
          getChannel().newCall(getAskMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 健康探针
     * </pre>
     */
    public void health(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest request,
        io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getHealthMethod(), getCallOptions()), request, responseObserver);
    }
  }

  /**
   * A stub to allow clients to do synchronous rpc calls to service AiService.
   * <pre>
   * AI Worker 契约(v1 LangGraph 编排 1:1 保留,仅接口层 gRPC 化,N1 非目标)
   * 流式口径与探针 P1 结论一致:server-streaming 走 Nginx 需 grpc_read_timeout&gt;=300s。
   * </pre>
   */
  public static final class AiServiceBlockingStub
      extends io.grpc.stub.AbstractBlockingStub<AiServiceBlockingStub> {
    private AiServiceBlockingStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected AiServiceBlockingStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new AiServiceBlockingStub(channel, callOptions);
    }

    /**
     * <pre>
     * 抽取:文件 → 结构化数据(unary,v1 framework.extract 同步语义)
     * </pre>
     */
    public cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse extract(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getExtractMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 模板抽取:样本图 → 强制 award 抽取器的结构化字段(unary,架构票;v1 extract-for-create 语义)
     * </pre>
     */
    public cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse extractTemplate(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getExtractTemplateMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 模板 prompt 生成:模板规则+样本文本 → 提示词(unary,架构票;v1 generate-prompt-for-create 语义)
     * </pre>
     */
    public cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse generatePrompt(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getGeneratePromptMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 抽取+审核全链:流式过程事件(node 进度/答案增量)+ 最终审核结论(server-streaming)
     * </pre>
     */
    public java.util.Iterator<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent> extractAndReview(
        cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest request) {
      return io.grpc.stub.ClientCalls.blockingServerStreamingCall(
          getChannel(), getExtractAndReviewMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * AI 问答(RAG):流式答案增量(server-streaming)
     * </pre>
     */
    public java.util.Iterator<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent> ask(
        cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest request) {
      return io.grpc.stub.ClientCalls.blockingServerStreamingCall(
          getChannel(), getAskMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 健康探针
     * </pre>
     */
    public cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse health(cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getHealthMethod(), getCallOptions(), request);
    }
  }

  /**
   * A stub to allow clients to do ListenableFuture-style rpc calls to service AiService.
   * <pre>
   * AI Worker 契约(v1 LangGraph 编排 1:1 保留,仅接口层 gRPC 化,N1 非目标)
   * 流式口径与探针 P1 结论一致:server-streaming 走 Nginx 需 grpc_read_timeout&gt;=300s。
   * </pre>
   */
  public static final class AiServiceFutureStub
      extends io.grpc.stub.AbstractFutureStub<AiServiceFutureStub> {
    private AiServiceFutureStub(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      super(channel, callOptions);
    }

    @java.lang.Override
    protected AiServiceFutureStub build(
        io.grpc.Channel channel, io.grpc.CallOptions callOptions) {
      return new AiServiceFutureStub(channel, callOptions);
    }

    /**
     * <pre>
     * 抽取:文件 → 结构化数据(unary,v1 framework.extract 同步语义)
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse> extract(
        cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getExtractMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 模板抽取:样本图 → 强制 award 抽取器的结构化字段(unary,架构票;v1 extract-for-create 语义)
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse> extractTemplate(
        cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getExtractTemplateMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 模板 prompt 生成:模板规则+样本文本 → 提示词(unary,架构票;v1 generate-prompt-for-create 语义)
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse> generatePrompt(
        cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getGeneratePromptMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 健康探针
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse> health(
        cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getHealthMethod(), getCallOptions()), request);
    }
  }

  private static final int METHODID_EXTRACT = 0;
  private static final int METHODID_EXTRACT_TEMPLATE = 1;
  private static final int METHODID_GENERATE_PROMPT = 2;
  private static final int METHODID_EXTRACT_AND_REVIEW = 3;
  private static final int METHODID_ASK = 4;
  private static final int METHODID_HEALTH = 5;

  private static final class MethodHandlers<Req, Resp> implements
      io.grpc.stub.ServerCalls.UnaryMethod<Req, Resp>,
      io.grpc.stub.ServerCalls.ServerStreamingMethod<Req, Resp>,
      io.grpc.stub.ServerCalls.ClientStreamingMethod<Req, Resp>,
      io.grpc.stub.ServerCalls.BidiStreamingMethod<Req, Resp> {
    private final AsyncService serviceImpl;
    private final int methodId;

    MethodHandlers(AsyncService serviceImpl, int methodId) {
      this.serviceImpl = serviceImpl;
      this.methodId = methodId;
    }

    @java.lang.Override
    @java.lang.SuppressWarnings("unchecked")
    public void invoke(Req request, io.grpc.stub.StreamObserver<Resp> responseObserver) {
      switch (methodId) {
        case METHODID_EXTRACT:
          serviceImpl.extract((cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest) request,
              (io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse>) responseObserver);
          break;
        case METHODID_EXTRACT_TEMPLATE:
          serviceImpl.extractTemplate((cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest) request,
              (io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse>) responseObserver);
          break;
        case METHODID_GENERATE_PROMPT:
          serviceImpl.generatePrompt((cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest) request,
              (io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse>) responseObserver);
          break;
        case METHODID_EXTRACT_AND_REVIEW:
          serviceImpl.extractAndReview((cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest) request,
              (io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent>) responseObserver);
          break;
        case METHODID_ASK:
          serviceImpl.ask((cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest) request,
              (io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent>) responseObserver);
          break;
        case METHODID_HEALTH:
          serviceImpl.health((cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest) request,
              (io.grpc.stub.StreamObserver<cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse>) responseObserver);
          break;
        default:
          throw new AssertionError();
      }
    }

    @java.lang.Override
    @java.lang.SuppressWarnings("unchecked")
    public io.grpc.stub.StreamObserver<Req> invoke(
        io.grpc.stub.StreamObserver<Resp> responseObserver) {
      switch (methodId) {
        default:
          throw new AssertionError();
      }
    }
  }

  public static final io.grpc.ServerServiceDefinition bindService(AsyncService service) {
    return io.grpc.ServerServiceDefinition.builder(getServiceDescriptor())
        .addMethod(
          getExtractMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest,
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractResponse>(
                service, METHODID_EXTRACT)))
        .addMethod(
          getExtractTemplateMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateRequest,
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractTemplateResponse>(
                service, METHODID_EXTRACT_TEMPLATE)))
        .addMethod(
          getGeneratePromptMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptRequest,
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.GeneratePromptResponse>(
                service, METHODID_GENERATE_PROMPT)))
        .addMethod(
          getExtractAndReviewMethod(),
          io.grpc.stub.ServerCalls.asyncServerStreamingCall(
            new MethodHandlers<
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.ExtractRequest,
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.WorkflowEvent>(
                service, METHODID_EXTRACT_AND_REVIEW)))
        .addMethod(
          getAskMethod(),
          io.grpc.stub.ServerCalls.asyncServerStreamingCall(
            new MethodHandlers<
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AskRequest,
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.AnswerEvent>(
                service, METHODID_ASK)))
        .addMethod(
          getHealthMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthRequest,
              cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.HealthResponse>(
                service, METHODID_HEALTH)))
        .build();
  }

  private static abstract class AiServiceBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoFileDescriptorSupplier, io.grpc.protobuf.ProtoServiceDescriptorSupplier {
    AiServiceBaseDescriptorSupplier() {}

    @java.lang.Override
    public com.google.protobuf.Descriptors.FileDescriptor getFileDescriptor() {
      return cn.iocoder.yudao.module.business.framework.grpc.awardie.ai.AiServiceProto.getDescriptor();
    }

    @java.lang.Override
    public com.google.protobuf.Descriptors.ServiceDescriptor getServiceDescriptor() {
      return getFileDescriptor().findServiceByName("AiService");
    }
  }

  private static final class AiServiceFileDescriptorSupplier
      extends AiServiceBaseDescriptorSupplier {
    AiServiceFileDescriptorSupplier() {}
  }

  private static final class AiServiceMethodDescriptorSupplier
      extends AiServiceBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoMethodDescriptorSupplier {
    private final java.lang.String methodName;

    AiServiceMethodDescriptorSupplier(java.lang.String methodName) {
      this.methodName = methodName;
    }

    @java.lang.Override
    public com.google.protobuf.Descriptors.MethodDescriptor getMethodDescriptor() {
      return getServiceDescriptor().findMethodByName(methodName);
    }
  }

  private static volatile io.grpc.ServiceDescriptor serviceDescriptor;

  public static io.grpc.ServiceDescriptor getServiceDescriptor() {
    io.grpc.ServiceDescriptor result = serviceDescriptor;
    if (result == null) {
      synchronized (AiServiceGrpc.class) {
        result = serviceDescriptor;
        if (result == null) {
          serviceDescriptor = result = io.grpc.ServiceDescriptor.newBuilder(SERVICE_NAME)
              .setSchemaDescriptor(new AiServiceFileDescriptorSupplier())
              .addMethod(getExtractMethod())
              .addMethod(getExtractTemplateMethod())
              .addMethod(getGeneratePromptMethod())
              .addMethod(getExtractAndReviewMethod())
              .addMethod(getAskMethod())
              .addMethod(getHealthMethod())
              .build();
        }
      }
    }
    return result;
  }
}
