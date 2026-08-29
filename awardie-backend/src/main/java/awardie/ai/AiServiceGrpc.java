package awardie.ai;

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
  private static volatile io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.ExtractRequest,
      awardie.ai.AiServiceOuterClass.ExtractResponse> getExtractMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "Extract",
      requestType = awardie.ai.AiServiceOuterClass.ExtractRequest.class,
      responseType = awardie.ai.AiServiceOuterClass.ExtractResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.ExtractRequest,
      awardie.ai.AiServiceOuterClass.ExtractResponse> getExtractMethod() {
    io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.ExtractRequest, awardie.ai.AiServiceOuterClass.ExtractResponse> getExtractMethod;
    if ((getExtractMethod = AiServiceGrpc.getExtractMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getExtractMethod = AiServiceGrpc.getExtractMethod) == null) {
          AiServiceGrpc.getExtractMethod = getExtractMethod =
              io.grpc.MethodDescriptor.<awardie.ai.AiServiceOuterClass.ExtractRequest, awardie.ai.AiServiceOuterClass.ExtractResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "Extract"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  awardie.ai.AiServiceOuterClass.ExtractRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  awardie.ai.AiServiceOuterClass.ExtractResponse.getDefaultInstance()))
              .setSchemaDescriptor(new AiServiceMethodDescriptorSupplier("Extract"))
              .build();
        }
      }
    }
    return getExtractMethod;
  }

  private static volatile io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.ExtractRequest,
      awardie.ai.AiServiceOuterClass.WorkflowEvent> getExtractAndReviewMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "ExtractAndReview",
      requestType = awardie.ai.AiServiceOuterClass.ExtractRequest.class,
      responseType = awardie.ai.AiServiceOuterClass.WorkflowEvent.class,
      methodType = io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
  public static io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.ExtractRequest,
      awardie.ai.AiServiceOuterClass.WorkflowEvent> getExtractAndReviewMethod() {
    io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.ExtractRequest, awardie.ai.AiServiceOuterClass.WorkflowEvent> getExtractAndReviewMethod;
    if ((getExtractAndReviewMethod = AiServiceGrpc.getExtractAndReviewMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getExtractAndReviewMethod = AiServiceGrpc.getExtractAndReviewMethod) == null) {
          AiServiceGrpc.getExtractAndReviewMethod = getExtractAndReviewMethod =
              io.grpc.MethodDescriptor.<awardie.ai.AiServiceOuterClass.ExtractRequest, awardie.ai.AiServiceOuterClass.WorkflowEvent>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "ExtractAndReview"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  awardie.ai.AiServiceOuterClass.ExtractRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  awardie.ai.AiServiceOuterClass.WorkflowEvent.getDefaultInstance()))
              .setSchemaDescriptor(new AiServiceMethodDescriptorSupplier("ExtractAndReview"))
              .build();
        }
      }
    }
    return getExtractAndReviewMethod;
  }

  private static volatile io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.AskRequest,
      awardie.ai.AiServiceOuterClass.AnswerEvent> getAskMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "Ask",
      requestType = awardie.ai.AiServiceOuterClass.AskRequest.class,
      responseType = awardie.ai.AiServiceOuterClass.AnswerEvent.class,
      methodType = io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
  public static io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.AskRequest,
      awardie.ai.AiServiceOuterClass.AnswerEvent> getAskMethod() {
    io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.AskRequest, awardie.ai.AiServiceOuterClass.AnswerEvent> getAskMethod;
    if ((getAskMethod = AiServiceGrpc.getAskMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getAskMethod = AiServiceGrpc.getAskMethod) == null) {
          AiServiceGrpc.getAskMethod = getAskMethod =
              io.grpc.MethodDescriptor.<awardie.ai.AiServiceOuterClass.AskRequest, awardie.ai.AiServiceOuterClass.AnswerEvent>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.SERVER_STREAMING)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "Ask"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  awardie.ai.AiServiceOuterClass.AskRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  awardie.ai.AiServiceOuterClass.AnswerEvent.getDefaultInstance()))
              .setSchemaDescriptor(new AiServiceMethodDescriptorSupplier("Ask"))
              .build();
        }
      }
    }
    return getAskMethod;
  }

  private static volatile io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.HealthRequest,
      awardie.ai.AiServiceOuterClass.HealthResponse> getHealthMethod;

  @io.grpc.stub.annotations.RpcMethod(
      fullMethodName = SERVICE_NAME + '/' + "Health",
      requestType = awardie.ai.AiServiceOuterClass.HealthRequest.class,
      responseType = awardie.ai.AiServiceOuterClass.HealthResponse.class,
      methodType = io.grpc.MethodDescriptor.MethodType.UNARY)
  public static io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.HealthRequest,
      awardie.ai.AiServiceOuterClass.HealthResponse> getHealthMethod() {
    io.grpc.MethodDescriptor<awardie.ai.AiServiceOuterClass.HealthRequest, awardie.ai.AiServiceOuterClass.HealthResponse> getHealthMethod;
    if ((getHealthMethod = AiServiceGrpc.getHealthMethod) == null) {
      synchronized (AiServiceGrpc.class) {
        if ((getHealthMethod = AiServiceGrpc.getHealthMethod) == null) {
          AiServiceGrpc.getHealthMethod = getHealthMethod =
              io.grpc.MethodDescriptor.<awardie.ai.AiServiceOuterClass.HealthRequest, awardie.ai.AiServiceOuterClass.HealthResponse>newBuilder()
              .setType(io.grpc.MethodDescriptor.MethodType.UNARY)
              .setFullMethodName(generateFullMethodName(SERVICE_NAME, "Health"))
              .setSampledToLocalTracing(true)
              .setRequestMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  awardie.ai.AiServiceOuterClass.HealthRequest.getDefaultInstance()))
              .setResponseMarshaller(io.grpc.protobuf.ProtoUtils.marshaller(
                  awardie.ai.AiServiceOuterClass.HealthResponse.getDefaultInstance()))
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
    default void extract(awardie.ai.AiServiceOuterClass.ExtractRequest request,
        io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.ExtractResponse> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getExtractMethod(), responseObserver);
    }

    /**
     * <pre>
     * 抽取+审核全链:流式过程事件(node 进度/答案增量)+ 最终审核结论(server-streaming)
     * </pre>
     */
    default void extractAndReview(awardie.ai.AiServiceOuterClass.ExtractRequest request,
        io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.WorkflowEvent> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getExtractAndReviewMethod(), responseObserver);
    }

    /**
     * <pre>
     * AI 问答(RAG):流式答案增量(server-streaming)
     * </pre>
     */
    default void ask(awardie.ai.AiServiceOuterClass.AskRequest request,
        io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.AnswerEvent> responseObserver) {
      io.grpc.stub.ServerCalls.asyncUnimplementedUnaryCall(getAskMethod(), responseObserver);
    }

    /**
     * <pre>
     * 健康探针
     * </pre>
     */
    default void health(awardie.ai.AiServiceOuterClass.HealthRequest request,
        io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.HealthResponse> responseObserver) {
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
    public void extract(awardie.ai.AiServiceOuterClass.ExtractRequest request,
        io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.ExtractResponse> responseObserver) {
      io.grpc.stub.ClientCalls.asyncUnaryCall(
          getChannel().newCall(getExtractMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 抽取+审核全链:流式过程事件(node 进度/答案增量)+ 最终审核结论(server-streaming)
     * </pre>
     */
    public void extractAndReview(awardie.ai.AiServiceOuterClass.ExtractRequest request,
        io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.WorkflowEvent> responseObserver) {
      io.grpc.stub.ClientCalls.asyncServerStreamingCall(
          getChannel().newCall(getExtractAndReviewMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * AI 问答(RAG):流式答案增量(server-streaming)
     * </pre>
     */
    public void ask(awardie.ai.AiServiceOuterClass.AskRequest request,
        io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.AnswerEvent> responseObserver) {
      io.grpc.stub.ClientCalls.asyncServerStreamingCall(
          getChannel().newCall(getAskMethod(), getCallOptions()), request, responseObserver);
    }

    /**
     * <pre>
     * 健康探针
     * </pre>
     */
    public void health(awardie.ai.AiServiceOuterClass.HealthRequest request,
        io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.HealthResponse> responseObserver) {
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
    public awardie.ai.AiServiceOuterClass.ExtractResponse extract(awardie.ai.AiServiceOuterClass.ExtractRequest request) {
      return io.grpc.stub.ClientCalls.blockingUnaryCall(
          getChannel(), getExtractMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 抽取+审核全链:流式过程事件(node 进度/答案增量)+ 最终审核结论(server-streaming)
     * </pre>
     */
    public java.util.Iterator<awardie.ai.AiServiceOuterClass.WorkflowEvent> extractAndReview(
        awardie.ai.AiServiceOuterClass.ExtractRequest request) {
      return io.grpc.stub.ClientCalls.blockingServerStreamingCall(
          getChannel(), getExtractAndReviewMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * AI 问答(RAG):流式答案增量(server-streaming)
     * </pre>
     */
    public java.util.Iterator<awardie.ai.AiServiceOuterClass.AnswerEvent> ask(
        awardie.ai.AiServiceOuterClass.AskRequest request) {
      return io.grpc.stub.ClientCalls.blockingServerStreamingCall(
          getChannel(), getAskMethod(), getCallOptions(), request);
    }

    /**
     * <pre>
     * 健康探针
     * </pre>
     */
    public awardie.ai.AiServiceOuterClass.HealthResponse health(awardie.ai.AiServiceOuterClass.HealthRequest request) {
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
    public com.google.common.util.concurrent.ListenableFuture<awardie.ai.AiServiceOuterClass.ExtractResponse> extract(
        awardie.ai.AiServiceOuterClass.ExtractRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getExtractMethod(), getCallOptions()), request);
    }

    /**
     * <pre>
     * 健康探针
     * </pre>
     */
    public com.google.common.util.concurrent.ListenableFuture<awardie.ai.AiServiceOuterClass.HealthResponse> health(
        awardie.ai.AiServiceOuterClass.HealthRequest request) {
      return io.grpc.stub.ClientCalls.futureUnaryCall(
          getChannel().newCall(getHealthMethod(), getCallOptions()), request);
    }
  }

  private static final int METHODID_EXTRACT = 0;
  private static final int METHODID_EXTRACT_AND_REVIEW = 1;
  private static final int METHODID_ASK = 2;
  private static final int METHODID_HEALTH = 3;

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
          serviceImpl.extract((awardie.ai.AiServiceOuterClass.ExtractRequest) request,
              (io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.ExtractResponse>) responseObserver);
          break;
        case METHODID_EXTRACT_AND_REVIEW:
          serviceImpl.extractAndReview((awardie.ai.AiServiceOuterClass.ExtractRequest) request,
              (io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.WorkflowEvent>) responseObserver);
          break;
        case METHODID_ASK:
          serviceImpl.ask((awardie.ai.AiServiceOuterClass.AskRequest) request,
              (io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.AnswerEvent>) responseObserver);
          break;
        case METHODID_HEALTH:
          serviceImpl.health((awardie.ai.AiServiceOuterClass.HealthRequest) request,
              (io.grpc.stub.StreamObserver<awardie.ai.AiServiceOuterClass.HealthResponse>) responseObserver);
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
              awardie.ai.AiServiceOuterClass.ExtractRequest,
              awardie.ai.AiServiceOuterClass.ExtractResponse>(
                service, METHODID_EXTRACT)))
        .addMethod(
          getExtractAndReviewMethod(),
          io.grpc.stub.ServerCalls.asyncServerStreamingCall(
            new MethodHandlers<
              awardie.ai.AiServiceOuterClass.ExtractRequest,
              awardie.ai.AiServiceOuterClass.WorkflowEvent>(
                service, METHODID_EXTRACT_AND_REVIEW)))
        .addMethod(
          getAskMethod(),
          io.grpc.stub.ServerCalls.asyncServerStreamingCall(
            new MethodHandlers<
              awardie.ai.AiServiceOuterClass.AskRequest,
              awardie.ai.AiServiceOuterClass.AnswerEvent>(
                service, METHODID_ASK)))
        .addMethod(
          getHealthMethod(),
          io.grpc.stub.ServerCalls.asyncUnaryCall(
            new MethodHandlers<
              awardie.ai.AiServiceOuterClass.HealthRequest,
              awardie.ai.AiServiceOuterClass.HealthResponse>(
                service, METHODID_HEALTH)))
        .build();
  }

  private static abstract class AiServiceBaseDescriptorSupplier
      implements io.grpc.protobuf.ProtoFileDescriptorSupplier, io.grpc.protobuf.ProtoServiceDescriptorSupplier {
    AiServiceBaseDescriptorSupplier() {}

    @java.lang.Override
    public com.google.protobuf.Descriptors.FileDescriptor getFileDescriptor() {
      return awardie.ai.AiServiceOuterClass.getDescriptor();
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
